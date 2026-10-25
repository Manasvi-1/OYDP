"""Run only against a disposable empty PostgreSQL database; never production."""
import os
from pathlib import Path
from uuid import uuid4
import shutil

import psycopg
import pytest

from scripts.migrate import migrate, provision_runtime, ROOT

DSN = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DSN, reason='TEST_DATABASE_URL is required for real PostgreSQL tests')
A, B = uuid4(), uuid4()
PA, PB = uuid4(), uuid4()
PASSWORD = 'synthetic-test-only-password-32-chars'


@pytest.fixture(scope='module', autouse=True)
def database():
    assert migrate(DSN)
    assert migrate(DSN) == []
    provision_runtime(DSN, PASSWORD)
    with psycopg.connect(DSN) as conn:
        conn.execute('INSERT INTO properties(id,tenant_id,label,jurisdiction,created_by) VALUES (%s,%s,\'A\',\'KA\',\'alice\'),(%s,%s,\'B\',\'KA\',\'bob\')', (PA,A,PB,B))
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'alice','owner'),(%s,'bob','viewer')", (A,B))


def runtime(tenant=None, subject='alice'):
    from psycopg.conninfo import make_conninfo
    conn = psycopg.connect(make_conninfo(DSN, user='oydp_app', password=PASSWORD))
    if tenant:
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
    conn.execute("SELECT set_config('app.subject_id', %s, true)", (subject,))
    return conn


def test_runtime_role_has_no_bypass_or_ownership():
    with runtime(A) as conn:
        assert conn.execute('SELECT current_user').fetchone()[0] == 'oydp_app'
        assert conn.execute("SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone() == (False,False,False,False)
        assert not conn.execute('SELECT 1 FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)').fetchone()


def test_no_context_sees_nothing():
    with runtime() as conn:
        assert conn.execute('SELECT id FROM properties').fetchall() == []


def test_cross_tenant_read_update_delete():
    with runtime(A) as conn:
        assert conn.execute('SELECT id FROM properties').fetchall() == [(PA,)]
        assert conn.execute("UPDATE properties SET label='stolen' WHERE id=%s", (PB,)).rowcount == 0
        assert conn.execute('DELETE FROM properties WHERE id=%s', (PB,)).rowcount == 0


def test_cross_tenant_insert_denied():
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("INSERT INTO properties(tenant_id,label,jurisdiction) VALUES (%s,'bad','KA')", (B,))


def test_tenant_reassignment_denied():
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute('UPDATE properties SET tenant_id=%s WHERE id=%s', (B,PA))


def test_membership_subject_filter():
    with runtime(B, 'alice') as conn:
        assert conn.execute('SELECT role FROM tenant_memberships').fetchall() == []
    with runtime(B, 'bob') as conn:
        assert conn.execute('SELECT role FROM tenant_memberships').fetchall() == [('viewer',)]


def test_membership_self_grant_denied():
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'mallory','owner')", (A,))


def test_context_clears_after_commit():
    with runtime(A) as conn:
        conn.commit()
        assert conn.execute('SELECT id FROM properties').fetchall() == []


def test_provenance_cross_tenant_denied():
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind) VALUES (%s,%s,'claim','test','user_claim')", (A,PB))


def test_privileged_path_cannot_break_lineage():
    with pytest.raises(psycopg.errors.ForeignKeyViolation), psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind) VALUES (%s,%s,'claim','test','user_claim')", (A,PB))


def test_valid_provenance():
    with runtime(A) as conn:
        conn.execute("INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind) VALUES (%s,%s,'claim','test','user_claim')", (A,PA))
        assert conn.execute('SELECT property_id FROM evidence_assertions').fetchall() == [(PA,)]
    with runtime(B) as conn:
        assert conn.execute('SELECT id FROM evidence_assertions').fetchall() == []


def test_checksum_drift_rejected(tmp_path):
    for p in ROOT.glob('*.sql'):
        shutil.copy(p, tmp_path)
    path = tmp_path / '001_property_identity.sql'
    path.write_text(path.read_text() + '\n-- changed\n')
    with pytest.raises(ValueError, match='checksum mismatch'):
        migrate(DSN, tmp_path)


def test_failed_migration_rolls_back(tmp_path):
    for p in ROOT.glob('*.sql'):
        shutil.copy(p, tmp_path)
    (tmp_path / '999_failure.sql').write_text('CREATE TABLE rollback_probe(id int); SELECT missing_column;')
    with pytest.raises(psycopg.errors.UndefinedColumn):
        migrate(DSN, tmp_path)
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT to_regclass('public.rollback_probe')").fetchone() == (None,)
        assert not conn.execute("SELECT 1 FROM schema_migrations WHERE name='999_failure.sql'").fetchone()


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from psycopg.conninfo import make_conninfo
    from app.main import app
    from app.auth import verified_subject, require_mfa
    monkeypatch.setenv('DATABASE_URL', make_conninfo(DSN, user='oydp_app', password=PASSWORD))
    # Cryptographic validation has separate RSA tests. These exercise the real API,
    # trusted membership lookup and PostgreSQL RLS using an injected verified subject.
    app.dependency_overrides[verified_subject] = lambda: 'alice'
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_api_create_read_and_cross_tenant(api):
    headers = {'X-Tenant-ID': str(A)}
    r = api.post('/v1/properties', headers=headers, json={'label':'New property','jurisdiction':'KA'})
    assert r.status_code == 201, r.text
    property_id = r.json()['id']
    assert r.json()['tenant_id'] == str(A)
    with runtime(A) as conn:
        assert conn.execute("SELECT actor_subject,event_type FROM property_audit_events WHERE property_id=%s", (property_id,)).fetchall() == [('alice','property.created')]
    with runtime(B) as conn:
        assert conn.execute('SELECT id FROM property_audit_events').fetchall() == []
    assert api.get('/v1/properties/'+property_id, headers=headers).json()['label'] == 'New property'
    assert api.get('/v1/properties/'+str(PB), headers=headers).status_code == 404
    assert api.get('/v1/properties/'+property_id, headers={'X-Tenant-ID':str(B)}).status_code == 403
    assert api.post('/v1/properties', headers={'X-Tenant-ID':str(B)}, json={'label':'bad','jurisdiction':'KA'}).status_code == 403


def test_api_viewer_cannot_create(api):
    from app.main import app
    from app.auth import verified_subject
    app.dependency_overrides[verified_subject] = lambda: 'bob'
    headers = {'X-Tenant-ID':str(B)}
    assert api.get('/v1/properties/'+str(PB), headers=headers).status_code == 200
    assert api.post('/v1/properties', headers=headers, json={'label':'bad','jurisdiction':'KA'}).status_code == 403


def test_api_revoked_membership_denied(api):
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'temporary','viewer')", (B,))
    from app.main import app
    from app.auth import verified_subject
    app.dependency_overrides[verified_subject] = lambda: 'temporary'
    headers = {'X-Tenant-ID':str(B)}
    assert api.get('/v1/properties/'+str(PB), headers=headers).status_code == 404
    with psycopg.connect(DSN) as conn:
        conn.execute("DELETE FROM tenant_memberships WHERE tenant_id=%s AND subject_id='temporary'", (B,))
    assert api.get('/v1/properties/'+str(PB), headers=headers).status_code == 403


@pytest.mark.parametrize('payload', [
    {'label':' ','jurisdiction':'KA'},
    {'label':'ok','jurisdiction':'KA','tenant_id':str(B)},
    {'label':'ok','jurisdiction':'KA','id':str(PB)},
])
def test_api_rejects_invalid_or_server_owned_fields(api, payload):
    assert api.post('/v1/properties', headers={'X-Tenant-ID':str(A)}, json=payload).status_code == 422


def test_api_rejects_privileged_database(api, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', DSN)
    assert api.get('/v1/properties/'+str(PA), headers={'X-Tenant-ID':str(A)}).status_code == 503


def test_api_full_signed_token_journey(api, monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from cryptography.hazmat.primitives.asymmetric import rsa
    import jwt
    from app.main import app
    app.dependency_overrides.clear()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv('OIDC_ISSUER', 'https://id.example.test')
    monkeypatch.setenv('OIDC_AUDIENCE', 'oydp-api')
    monkeypatch.setenv('OIDC_JWKS_URL', 'https://id.example.test/keys')
    class Keys:
        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=key.public_key())
    monkeypatch.setattr('app.auth.jwks_client', lambda _: Keys())
    now = int(datetime.now(timezone.utc).timestamp())
    token = jwt.encode(dict(iss='https://id.example.test',aud='oydp-api',sub='alice',iat=now,exp=now+300,amr=['mfa']), key,
                       algorithm='RS256', headers={'kid':'test','typ':'at+jwt'})
    headers = {'X-Tenant-ID':str(A), 'Authorization':'Bearer '+token}
    r = api.post('/v1/properties', headers=headers, json={'label':'Signed request','jurisdiction':'KA'})
    assert r.status_code == 201, r.text
    assert api.get('/v1/properties/'+r.json()['id'], headers=headers).status_code == 200
    assert api.get('/v1/properties/'+str(PA), headers={'X-Tenant-ID':str(A)}).status_code == 401


@pytest.mark.parametrize('statement', ["UPDATE property_audit_events SET actor_subject='mallory'", "DELETE FROM property_audit_events"])
def test_audit_mutation_denied(statement):
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute(statement)


def test_audit_failure_rolls_back_property(api):
    # Abort the audit insert in a disposable DB; verify no orphan property commits.
    with psycopg.connect(DSN) as conn:
        conn.execute('REVOKE INSERT ON property_audit_events FROM oydp_app')
    try:
        r = api.post('/v1/properties', headers={'X-Tenant-ID':str(A)}, json={'label':'must-rollback','jurisdiction':'KA'})
        assert r.status_code == 503
        with runtime(A) as conn:
            assert conn.execute("SELECT id FROM properties WHERE label='must-rollback'").fetchall() == []
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('GRANT INSERT ON property_audit_events TO oydp_app')


@pytest.fixture
def private_record(api):
    from datetime import datetime, timedelta, timezone
    from app.main import app
    from app.auth import verified_subject
    peer = 'peer-' + str(uuid4())
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,%s,'viewer')", (A,peer))
    headers = {'X-Tenant-ID':str(A)}
    r = api.post('/v1/properties', headers=headers, json={'label':'Private record','jurisdiction':'KA'})
    assert r.status_code == 201, r.text
    pid = r.json()['id']
    expiry = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    def as_subject(subject):
        app.dependency_overrides[verified_subject] = lambda: subject
    return pid, peer, headers, {'recipient_subject':peer, 'expires_at':expiry}, as_subject


def test_same_tenant_private_and_audit_hidden(api, private_record):
    pid,peer,h,data,as_subject = private_record
    as_subject(peer)
    assert api.get('/v1/properties/'+pid, headers=h).status_code == 404
    with runtime(A,peer) as conn:
        assert conn.execute('SELECT id FROM properties').fetchall() == []
        assert conn.execute('SELECT id FROM property_audit_events').fetchall() == []


def test_canonical_share_read_revoke(api, private_record):
    pid,peer,h,data,as_subject = private_record
    url = '/v1/properties/'+pid+'/access'
    assert api.put(url,headers=h,json=data).json() == {'changed':True}
    assert api.put(url,headers=h,json=data).json() == {'changed':False}
    as_subject(peer)
    assert api.get('/v1/properties/'+pid,headers=h).status_code == 200
    # A read grant cannot authorize evidence writes or resharing.
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A,peer) as conn:
        conn.execute("INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind) VALUES(%s,%s,'claim','not allowed','user_claim')",(A,pid))
    assert api.put(url,headers=h,json={'recipient_subject':'alice','expires_at':data['expires_at']}).status_code == 404
    as_subject('alice')
    assert api.request('DELETE',url,headers=h,json={'recipient_subject':peer}).json() == {'changed':True}
    assert api.request('DELETE',url,headers=h,json={'recipient_subject':peer}).json() == {'changed':False}
    as_subject(peer)
    assert api.get('/v1/properties/'+pid,headers=h).status_code == 404
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT event_type FROM property_audit_events WHERE property_id=%s ORDER BY created_at,id",(pid,)).fetchall() == [('property.created',),('access.granted',),('access.revoked',)]


@pytest.mark.parametrize('recipient', ['alice','nonmember','bob'])
def test_invalid_share_target_denied(api, private_record, recipient):
    pid,peer,h,data,_ = private_record
    data['recipient_subject'] = recipient
    assert api.put('/v1/properties/'+pid+'/access',headers=h,json=data).status_code == 404


@pytest.mark.parametrize('days', [-1,31])
def test_canonical_invalid_expiry(api, private_record, days):
    from datetime import datetime,timedelta,timezone
    pid,peer,h,data,_ = private_record
    data['expires_at']=(datetime.now(timezone.utc)+timedelta(days=days)).isoformat()
    assert api.put('/v1/properties/'+pid+'/access',headers=h,json=data).status_code == 422


def test_expired_grant_denied(api, private_record):
    pid,peer,h,data,as_subject = private_record
    assert api.put('/v1/properties/'+pid+'/access',headers=h,json=data).status_code == 200
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE property_read_grants SET expires_at=clock_timestamp()-interval '1 second' WHERE property_id=%s",(pid,))
    as_subject(peer)
    assert api.get('/v1/properties/'+pid,headers=h).status_code == 404


def test_granted_member_removal_denies_access(api, private_record):
    pid,peer,h,data,as_subject = private_record
    assert api.put('/v1/properties/'+pid+'/access',headers=h,json=data).status_code == 200
    with psycopg.connect(DSN) as conn:
        conn.execute('DELETE FROM tenant_memberships WHERE tenant_id=%s AND subject_id=%s',(A,peer))
    as_subject(peer)
    assert api.get('/v1/properties/'+pid,headers=h).status_code == 403
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES(%s,%s,'viewer')",(A,peer))
    assert api.get('/v1/properties/'+pid,headers=h).status_code == 404


def test_no_mfa_sensitive_routes_denied(api, private_record):
    from app.main import app
    from app.auth import require_mfa
    from fastapi import HTTPException
    pid,peer,h,data,_ = private_record
    def denied(): raise HTTPException(403,'MFA required')
    app.dependency_overrides[require_mfa] = denied
    assert api.post('/v1/properties',headers=h,json={'label':'blocked','jurisdiction':'KA'}).status_code == 403
    assert api.put('/v1/properties/'+pid+'/access',headers=h,json=data).status_code == 403
    assert api.request('DELETE','/v1/properties/'+pid+'/access',headers=h,json={'recipient_subject':peer}).status_code == 403


def test_share_audit_failure_is_atomic(api, private_record):
    pid,peer,h,data,_ = private_record
    with psycopg.connect(DSN) as conn:
        conn.execute("ALTER TABLE property_audit_events ADD CONSTRAINT injected_grant_failure CHECK(event_type<>'access.granted') NOT VALID")
    try:
        assert api.put('/v1/properties/'+pid+'/access',headers=h,json=data).status_code == 503
        with psycopg.connect(DSN) as conn:
            assert not conn.execute('SELECT 1 FROM property_read_grants WHERE property_id=%s',(pid,)).fetchone()
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('ALTER TABLE property_audit_events DROP CONSTRAINT injected_grant_failure')


def test_cannot_forge_grants_directly(api, private_record):
    pid,peer,_,data,_ = private_record
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A,peer) as conn:
        conn.execute('INSERT INTO property_read_grants VALUES(%s,%s,%s,%s,false)',(A,pid,peer,data['expires_at']))


def test_unattributed_property_fails_closed(api):
    pid=uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO properties(id,tenant_id,label,jurisdiction,created_by) VALUES(%s,%s,'Legacy unknown','KA',NULL)",(pid,A))
    assert api.get('/v1/properties/'+str(pid),headers={'X-Tenant-ID':str(A)}).status_code == 404


def test_access_function_privileges():
    with psycopg.connect(DSN) as conn:
        row=conn.execute("SELECT prosecdef,proconfig,NOT EXISTS(SELECT 1 FROM aclexplode(proacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE') FROM pg_proc WHERE oid='public.set_property_read_access(uuid,uuid,text,timestamptz)'::regprocedure").fetchone()
        assert row == (True,['search_path=pg_catalog, pg_temp'],True)


def test_canonical_revocation_waits_for_grant_reader(api, private_record):
    pid,peer,h,data,_ = private_record
    assert api.put('/v1/properties/'+pid+'/access',headers=h,json=data).status_code == 200
    with runtime(A,peer) as reader:
        assert reader.execute('SELECT 1 FROM property_read_grants WHERE property_id=%s FOR SHARE',(pid,)).fetchone()
        with pytest.raises(psycopg.errors.LockNotAvailable), runtime(A) as revoker:
            revoker.execute("SET LOCAL lock_timeout='100ms'")
            revoker.execute('SELECT public.set_property_read_access(%s,%s,%s,NULL)',(A,pid,peer))
    assert api.request('DELETE','/v1/properties/'+pid+'/access',headers=h,json={'recipient_subject':peer}).status_code == 200


def test_migration_attributes_only_audited_records(tmp_path):
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    name='oydp_upgrade_'+uuid4().hex
    upgrade=make_conninfo(DSN, dbname=name)
    with psycopg.connect(DSN,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    try:
        for path in ROOT.glob('*.sql'):
            if path.name<'006': shutil.copy(path,tmp_path)
        migrate(upgrade,tmp_path)
        known,unknown=uuid4(),uuid4()
        with psycopg.connect(upgrade) as conn:
            conn.execute("INSERT INTO tenant_memberships VALUES(%s,'alice','owner')",(A,))
            for pid in (known,unknown):
                conn.execute("INSERT INTO properties(id,tenant_id,label,jurisdiction) VALUES(%s,%s,'Legacy','KA')",(pid,A))
            conn.execute("INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type) VALUES(%s,%s,'alice','property.created')",(A,known))
        assert migrate(upgrade)==['006_private_property_access.sql']
        provision_runtime(upgrade,PASSWORD)
        with psycopg.connect(make_conninfo(upgrade,user='oydp_app',password=PASSWORD)) as conn:
            conn.execute("SELECT set_config('app.tenant_id',%s,true),set_config('app.subject_id','alice',true)",(str(A),))
            assert conn.execute('SELECT id,created_by FROM properties').fetchall()==[(known,'alice')]
    finally:
        with psycopg.connect(DSN,autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
