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


def test_legacy_evidence_assertions_frozen_for_runtime():
    # Active claims use record_property_claim; evidence_assertions DML is revoked.
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind) VALUES (%s,%s,'claim','test','user_claim')", (A,PA))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind) VALUES (%s,%s,'claim','test','user_claim')", (A,PB))


def test_privileged_path_cannot_break_lineage():
    with pytest.raises(psycopg.errors.ForeignKeyViolation), psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind) VALUES (%s,%s,'claim','test','user_claim')", (A,PB))


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
    token = jwt.encode(dict(iss='https://id.example.test',aud='oydp-api',sub='alice',iat=now,exp=now+300,
                            auth_time=now,amr=['mfa']), key,
                       algorithm='RS256', headers={'kid':'test','typ':'at+jwt'})
    headers = {'X-Tenant-ID':str(A), 'Authorization':'Bearer '+token}
    r = api.post('/v1/properties', headers=headers, json={'label':'Signed request','jurisdiction':'KA'})
    assert r.status_code == 201, r.text
    assert api.get('/v1/properties/'+r.json()['id'], headers=headers).status_code == 200
    claims_url='/v1/properties/'+r.json()['id']+'/claims'
    claim=api.post(claims_url,headers=headers,json={'statement':'Signed and explicitly unverified'})
    assert claim.status_code==201,claim.text
    assert claim.json()['created_by']=='alice' and claim.json()['verification_status']=='unverified'
    assert api.get(claims_url,headers=headers).json()['items'][0]['id']==claim.json()['id']
    assert r.json()['id'] in [item['id'] for item in api.get('/v1/properties',headers=headers).json()['items']]
    assert api.post(claims_url,headers={'X-Tenant-ID':str(A)},json={'statement':'No token'}).status_code==401
    assert api.get('/v1/properties/'+str(PA), headers={'X-Tenant-ID':str(A)}).status_code == 401


@pytest.mark.parametrize('statement', ["UPDATE property_audit_events SET actor_subject='mallory'", "DELETE FROM property_audit_events"])
def test_audit_mutation_denied(statement):
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute(statement)


def test_audit_failure_rolls_back_property(api):
    # Abort the gated audit helper; verify no orphan property commits.
    with psycopg.connect(DSN) as conn:
        conn.execute('REVOKE EXECUTE ON FUNCTION public.record_property_created_audit(uuid,uuid) FROM oydp_app')
    try:
        r = api.post('/v1/properties', headers={'X-Tenant-ID':str(A)}, json={'label':'must-rollback','jurisdiction':'KA'})
        assert r.status_code == 503
        with runtime(A) as conn:
            assert conn.execute("SELECT id FROM properties WHERE label='must-rollback'").fetchall() == []
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('GRANT EXECUTE ON FUNCTION public.record_property_created_audit(uuid,uuid) TO oydp_app')


def test_runtime_cannot_forge_property_audit_events():
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute(
            "INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type) VALUES(%s,%s,'alice','property.created')",
            (A, PA),
        )


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
    assert api.patch('/v1/properties/'+pid,headers=h,json={'label':'blocked','jurisdiction':'KA'}).status_code == 403
    assert api.put('/v1/properties/'+pid+'/writers',headers=h,json=data).status_code == 403
    assert api.request('DELETE','/v1/properties/'+pid+'/writers',headers=h,json={'recipient_subject':peer}).status_code == 403
    assert api.post('/v1/properties/'+pid+'/identifiers', headers=h, json={'scheme':'survey','identifier_value':'S-1'}).status_code == 403
    assert api.post('/v1/sources', headers=h, json={'name':'Blocked source','origin':'user_supplied','jurisdiction':'KA'}).status_code == 403
    assert api.post('/v1/sources/'+str(uuid4())+'/withdrawal', headers=h, json={'reason':'Blocked'}).status_code == 403
    assert api.post('/v1/properties/'+pid+'/reviews', headers=h, json={'disposition':'recorded','statement':'Not title'}).status_code == 403
    assert api.post('/v1/properties/'+pid+'/consents', headers=h, json={'purpose':'passport_export'}).status_code == 403
    assert api.request('DELETE', '/v1/properties/'+pid+'/consents', headers=h, json={'purpose':'passport_export'}).status_code == 403
    denied_export = api.post('/v1/properties/'+pid+'/exports', headers=h)
    assert denied_export.status_code == 403
    assert 'Private record' not in denied_export.text


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
        assert migrate(upgrade)==['006_private_property_access.sql','007_attributed_claims.sql','008_property_corrections.sql','009_correction_single_record.sql','010_document_quarantine.sql','011_write_grant_pages.sql','012_trusted_evidence.sql','013_audit_outbox.sql','014_diligence_requests.sql','015_claim_source_attribution.sql','016_document_attribution.sql','017_document_identifier_attribution.sql','018_review_claim_attribution.sql','019_review_document_identifier_attribution.sql','020_runtime_audit_and_source_gates.sql']
        provision_runtime(upgrade,PASSWORD)
        with psycopg.connect(make_conninfo(upgrade,user='oydp_app',password=PASSWORD)) as conn:
            conn.execute("SELECT set_config('app.tenant_id',%s,true),set_config('app.subject_id','alice',true)",(str(A),))
            assert conn.execute('SELECT id,created_by FROM properties').fetchall()==[(known,'alice')]
    finally:
        with psycopg.connect(DSN,autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def test_downgraded_creator_cannot_share_or_write_evidence(api, private_record):
    pid,peer,h,data,_ = private_record
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE tenant_memberships SET role='viewer' WHERE tenant_id=%s AND subject_id='alice'",(A,))
    try:
        assert api.get('/v1/properties/'+pid,headers=h).status_code == 200
        assert api.put('/v1/properties/'+pid+'/access',headers=h,json=data).status_code == 404
        with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
            conn.execute("INSERT INTO evidence_assertions(tenant_id,property_id,assertion_type,assertion_text,source_kind) VALUES(%s,%s,'claim','denied after downgrade','user_claim')",(A,pid))
        with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
            conn.execute("INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type) VALUES(%s,%s,'alice','diligence.noted')",(A,pid))
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute("UPDATE tenant_memberships SET role='owner' WHERE tenant_id=%s AND subject_id='alice'",(A,))


@pytest.fixture
def discovery(api):
    from app.main import app
    from app.auth import verified_subject
    tenant=uuid4()
    owner='creator-'+str(uuid4());reader='reader-'+str(uuid4())
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES(%s,%s,'owner'),(%s,%s,'viewer')",(tenant,owner,tenant,reader))
    def as_subject(subject): app.dependency_overrides[verified_subject]=lambda:subject
    as_subject(owner)
    h={'X-Tenant-ID':str(tenant)}
    def create(label='Candidate'):
        response=api.post('/v1/properties',headers=h,json={'label':label,'jurisdiction':'KA'})
        assert response.status_code==201,response.text
        return response.json()['id']
    return tenant,owner,reader,h,create,as_subject


def test_property_pages_empty_ties_and_bounded_navigation(api, discovery):
    tenant,owner,reader,h,create,as_subject=discovery
    assert api.get('/v1/properties',headers=h).json()=={'items':[],'next_cursor':None}
    ids=[create(str(i)) for i in range(5)]
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE properties SET created_at='2026-01-01T00:00:00Z' WHERE tenant_id=%s",(tenant,))
    found=[];cursor=None
    for _ in range(3):
        params={'limit':2}
        if cursor: params['cursor']=cursor
        response=api.get('/v1/properties',headers=h,params=params)
        assert response.status_code==200,response.text
        page=response.json();found += [r['id'] for r in page['items']];cursor=page['next_cursor']
        assert len(page['items'])<=2 and 'total' not in page
    assert found==sorted(ids,reverse=True) and cursor is None
    for value in [0,101]:
        assert api.get('/v1/properties',headers=h,params={'limit':value}).status_code==422


def test_property_cursor_does_not_duplicate_after_new_insert(api, discovery):
    tenant,_,_,h,create,_=discovery
    ids=[create() for _ in range(3)]
    first=api.get('/v1/properties',headers=h,params={'limit':1}).json()
    new_id=create('Newer after first page')
    after=api.get('/v1/properties',headers=h,params={'limit':100,'cursor':first['next_cursor']}).json()
    assert new_id not in [r['id'] for r in after['items']]
    assert set(ids)=={first['items'][0]['id']}|{r['id'] for r in after['items']}


def test_property_pages_apply_private_grants_and_revocation(api, discovery):
    from datetime import datetime,timedelta,timezone
    tenant,owner,reader,h,create,as_subject=discovery
    hidden,shared=create('Hidden'),create('Shared')
    data={'recipient_subject':reader,'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
    assert api.put('/v1/properties/'+shared+'/access',headers=h,json=data).status_code==200
    as_subject(reader)
    page=api.get('/v1/properties',headers=h).json()
    assert [r['id'] for r in page['items']]==[shared] and hidden not in str(page)
    as_subject(owner)
    assert api.request('DELETE','/v1/properties/'+shared+'/access',headers=h,json={'recipient_subject':reader}).status_code==200
    as_subject(reader)
    assert api.get('/v1/properties',headers=h).json()['items']==[]


def test_property_cursor_bound_to_tenant_and_subject(api, discovery):
    tenant,owner,reader,h,create,as_subject=discovery
    create();create()
    cursor=api.get('/v1/properties',headers=h,params={'limit':1}).json()['next_cursor']
    as_subject(reader)
    assert api.get('/v1/properties',headers=h,params={'cursor':cursor}).status_code==422
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES(%s,%s,'owner')",(B,owner))
    as_subject(owner)
    assert api.get('/v1/properties',headers={'X-Tenant-ID':str(B)},params={'cursor':cursor}).status_code==422


def test_claims_are_unverified_attributed_and_audited(api, discovery):
    tenant,owner,reader,h,create,_=discovery
    pid=create();url='/v1/properties/'+pid+'/claims'
    assert api.get(url,headers=h).json()=={'items':[],'next_cursor':None}
    response=api.post(url,headers=h,json={'statement':' Applicant claims an interest; not verified. '})
    assert response.status_code==201,response.text
    claim=response.json()
    assert claim['kind']=='user_claim' and claim['verification_status']=='unverified'
    assert claim['created_by']==owner and claim['property_id']==pid and claim['tenant_id']==str(tenant)
    assert claim['statement']=='Applicant claims an interest; not verified.'
    with runtime(tenant,owner) as conn:
        assert conn.execute("SELECT claim_id,actor_subject FROM property_audit_events WHERE event_type='claim.recorded' AND property_id=%s",(pid,)).fetchall()==[( __import__('uuid').UUID(claim['id']),owner)]
    assert api.get(url,headers=h).json()['items']==[claim]


@pytest.mark.parametrize('extra',[
    {'kind':'official_observation'}, {'verification_status':'verified'}, {'created_by':'forged'},
    {'tenant_id':str(B)}, {'property_id':str(PB)}, {'recorded_at':'2026-01-01T00:00:00Z'},
])
def test_claim_rejects_forged_metadata(api, discovery, extra):
    _,_,_,h,create,_=discovery;pid=create()
    assert api.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':'Unverified',**extra}).status_code==422


@pytest.mark.parametrize('statement',[' ','x'*10001])
def test_invalid_claim_statements(api, discovery, statement):
    _,_,_,h,create,_=discovery;pid=create()
    response=api.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':statement})
    assert response.status_code==422
    assert response.json()=={'detail':'Invalid request'}


def test_claim_pages_tied_times_and_cursor_scope(api, discovery):
    tenant,owner,reader,h,create,_=discovery
    pid,other=create(),create();url='/v1/properties/'+pid+'/claims'
    ids=[]
    for i in range(5):
        response=api.post(url,headers=h,json={'statement':str(i)})
        assert response.status_code==201,response.text
        ids.append(response.json()['id'])
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE property_claims SET recorded_at='2026-01-01T00:00:00Z' WHERE property_id=%s",(pid,))
    first=api.get(url,headers=h,params={'limit':2}).json()
    assert api.get('/v1/properties/'+other+'/claims',headers=h,params={'cursor':first['next_cursor']}).status_code==422
    assert api.get('/v1/properties',headers=h,params={'cursor':first['next_cursor']}).status_code==422
    found=[r['id'] for r in first['items']];cursor=first['next_cursor']
    while cursor:
        response=api.get(url,headers=h,params={'limit':2,'cursor':cursor})
        assert response.status_code==200,response.text
        page=response.json();found += [r['id'] for r in page['items']];cursor=page['next_cursor']
    assert found==sorted(ids,reverse=True)


def test_claim_readers_cannot_append_and_revocation_denies_history(api, discovery):
    from datetime import datetime,timedelta,timezone
    tenant,owner,reader,h,create,as_subject=discovery
    pid=create();url='/v1/properties/'+pid+'/claims'
    assert api.post(url,headers=h,json={'statement':'User claim only'}).status_code==201
    as_subject(reader)
    assert api.get(url,headers=h).status_code==404
    as_subject(owner)
    assert api.put('/v1/properties/'+pid+'/access',headers=h,json={'recipient_subject':reader,'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}).status_code==200
    as_subject(reader)
    assert len(api.get(url,headers=h).json()['items'])==1
    assert api.post(url,headers=h,json={'statement':'Forbidden reader claim'}).status_code==404
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(tenant,reader) as conn:
        conn.execute("INSERT INTO property_claims(tenant_id,property_id,statement) VALUES(%s,%s,'forbidden')",(tenant,pid))
    as_subject(owner)
    api.request('DELETE','/v1/properties/'+pid+'/access',headers=h,json={'recipient_subject':reader})
    as_subject(reader)
    assert api.get(url,headers=h).status_code==404


def test_claim_sensitive_actions_require_mfa_and_current_write_role(api, discovery):
    from app.main import app
    from app.auth import require_mfa
    from fastapi import HTTPException
    tenant,owner,_,h,create,_=discovery;pid=create();url='/v1/properties/'+pid+'/claims'
    def denied(): raise HTTPException(403,'MFA required')
    app.dependency_overrides[require_mfa]=denied
    assert api.post(url,headers=h,json={'statement':'No MFA'}).status_code==403
    app.dependency_overrides[require_mfa]=lambda:True
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE tenant_memberships SET role='viewer' WHERE tenant_id=%s AND subject_id=%s",(tenant,owner))
    assert api.post(url,headers=h,json={'statement':'No write role'}).status_code==403


def test_claim_audit_failure_rolls_back_ledger(api, discovery):
    tenant,owner,_,h,create,_=discovery;pid=create()
    with psycopg.connect(DSN) as conn:
        conn.execute("ALTER TABLE property_audit_events ADD CONSTRAINT injected_claim_failure CHECK(event_type<>'claim.recorded') NOT VALID")
    try:
        assert api.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':'Must roll back'}).status_code==503
        with runtime(tenant,owner) as conn:
            assert conn.execute('SELECT id FROM property_claims').fetchall()==[]
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('ALTER TABLE property_audit_events DROP CONSTRAINT injected_claim_failure')


@pytest.mark.parametrize('operation',["UPDATE property_claims SET statement='changed'",'DELETE FROM property_claims'])
def test_claims_are_immutable_for_runtime(api, discovery, operation):
    tenant,owner,_,h,create,_=discovery;pid=create()
    assert api.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':'Original'}).status_code==201
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(tenant,owner) as conn:
        conn.execute(operation)


def test_claim_audit_tenant_integrity_even_for_admin(api, discovery):
    tenant,owner,_,h,create,_=discovery;pid=create()
    claim=api.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':'Original'}).json()['id']
    with pytest.raises(psycopg.errors.ForeignKeyViolation), psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type,claim_id) VALUES(%s,%s,'bob','claim.recorded',%s)",(B,PB,claim))


def test_claim_database_rejects_official_classification(api, discovery):
    tenant,owner,_,_,create,_=discovery;pid=create()
    # Runtime cannot INSERT claims directly; table CHECK still refuses non-user_claim kinds.
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(tenant,owner) as conn:
        conn.execute("INSERT INTO property_claims(tenant_id,property_id,statement) VALUES(%s,%s,'blocked direct insert')",(tenant,pid))
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(DSN) as conn:
        conn.execute(
            "INSERT INTO property_claims(tenant_id,property_id,created_by,statement,kind) VALUES(%s,%s,%s,'Not official','official_observation')",
            (tenant, pid, owner),
        )


def test_claims_cross_tenant_hidden_even_with_valid_other_membership(api, discovery):
    tenant,owner,_,h,create,as_subject=discovery;pid=create()
    api.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':'Private claim'})
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES(%s,%s,'owner')",(B,owner))
    assert api.get('/v1/properties/'+pid+'/claims',headers={'X-Tenant-ID':str(B)}).status_code==404
    assert api.post('/v1/properties/'+pid+'/claims',headers={'X-Tenant-ID':str(B)},json={'statement':'Forged tenant'}).status_code==404


def test_valid_forged_navigation_cursor_does_not_authorize_records(api, discovery):
    from app.pagination import page_scope,encode_cursor
    from datetime import datetime,timezone
    tenant,owner,reader,h,create,as_subject=discovery;create()
    token=encode_cursor(page_scope('properties',str(tenant),reader),datetime(2099,1,1,tzinfo=timezone.utc),uuid4())
    as_subject(reader)
    assert api.get('/v1/properties',headers=h,params={'cursor':token}).json()['items']==[]


@pytest.mark.parametrize('kind',['properties','claims'])
def test_paginated_reads_serialize_with_grant_revocation(api, discovery, kind):
    from datetime import datetime,timedelta,timezone
    from app.main import list_properties,list_claims
    tenant,owner,reader,h,create,as_subject=discovery;pid=create()
    api.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':'Read transaction'})
    assert api.put('/v1/properties/'+pid+'/access',headers=h,json={'recipient_subject':reader,'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}).status_code==200
    with runtime(tenant,reader) as conn:
        from psycopg.rows import dict_row
        conn.row_factory = dict_row
        if kind=='properties': result=list_properties(access=(conn,'viewer'),limit=1,cursor=None)
        else: result=list_claims(__import__('uuid').UUID(pid),access=(conn,'viewer'),limit=1,cursor=None)
        assert len(result['items'])==1
        with pytest.raises(psycopg.errors.LockNotAvailable), runtime(tenant,owner) as revoker:
            revoker.execute("SET LOCAL lock_timeout='100ms'")
            revoker.execute('SELECT public.set_property_read_access(%s,%s,%s,NULL)',(tenant,pid,reader))
    assert api.request('DELETE','/v1/properties/'+pid+'/access',headers=h,json={'recipient_subject':reader}).status_code==200


def test_deferred_commit_failure_does_not_return_false_created(api, discovery):
    # Simulate a deferred DB constraint that fails only at COMMIT, after SQL succeeds.
    tenant,owner,_,h,create,_=discovery;pid=create()
    with psycopg.connect(DSN) as conn:
        conn.execute("""CREATE FUNCTION public.reject_claim_commit() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN RAISE EXCEPTION 'Synthetic deferred commit rejection'; END $$""")
        conn.execute("""CREATE CONSTRAINT TRIGGER reject_claim_commit AFTER INSERT ON property_claims
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.reject_claim_commit()""")
    try:
        response=api.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':'Must not acknowledge before commit'})
        assert response.status_code==503,response.text
        with runtime(tenant,owner) as conn:
            assert conn.execute('SELECT id FROM property_claims').fetchall()==[]
            assert conn.execute("SELECT id FROM property_audit_events WHERE event_type='claim.recorded'").fetchall()==[]
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('DROP TRIGGER reject_claim_commit ON property_claims')
            conn.execute('DROP FUNCTION public.reject_claim_commit()')


def _editor(name):
    with psycopg.connect(DSN) as conn:
        conn.execute('INSERT INTO tenant_memberships VALUES(%s,%s,\'editor\') ON CONFLICT DO NOTHING', (A, name))
    return name


def test_owner_correction_keeps_prior_values(api, private_record):
    pid, peer, h, data, _ = private_record
    first = api.patch('/v1/properties/'+pid, headers=h, json={'label':'Corrected label','jurisdiction':'Bengaluru Urban'})
    assert first.status_code == 200, first.text
    assert first.json()['changed'] is True and first.json()['label'] == 'Corrected label'
    again = api.patch('/v1/properties/'+pid, headers=h, json={'label':'Corrected label','jurisdiction':'Bengaluru Urban'})
    assert again.json()['changed'] is False
    history = api.get('/v1/properties/'+pid+'/corrections', headers=h).json()['items']
    assert len(history) == 1
    assert history[0]['previous_label'] == 'Private record' and history[0]['actor_subject'] == 'alice'
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT event_type FROM property_audit_events WHERE property_id=%s AND event_type='property.corrected'", (pid,)).fetchall() == [('property.corrected',)]
    assert api.patch('/v1/properties/'+pid, headers=h, json={'label':'x','jurisdiction':'KA','created_by':'mallory'}).status_code == 422


def test_delegated_editor_can_correct_and_append_only_while_granted(api, private_record):
    from datetime import datetime, timedelta, timezone
    pid, peer, h, data, as_subject = private_record
    editor = _editor('editor-'+str(uuid4()))
    expiry = (datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    grant = {'recipient_subject': editor, 'expires_at': expiry}
    assert api.put('/v1/properties/'+pid+'/writers', headers=h, json={'recipient_subject': peer, 'expires_at': expiry}).status_code == 404
    assert api.put('/v1/properties/'+pid+'/writers', headers=h, json=grant).json() == {'changed': True}
    assert api.put('/v1/properties/'+pid+'/writers', headers=h, json=grant).json() == {'changed': False}
    as_subject(editor)
    assert api.get('/v1/properties/'+pid+'/writers', headers=h).json()['items'][0]['recipient_subject'] == editor
    corrected = api.patch('/v1/properties/'+pid, headers=h, json={'label':'Editor correction','jurisdiction':'KA'})
    assert corrected.status_code == 200 and corrected.json()['changed'] is True
    claim = api.post('/v1/properties/'+pid+'/claims', headers=h, json={'statement':'Recorded by the delegated editor'})
    assert claim.status_code == 201 and claim.json()['created_by'] == editor and claim.json()['verification_status'] == 'unverified'
    assert api.put('/v1/properties/'+pid+'/access', headers=h, json=data).status_code == 404
    assert api.put('/v1/properties/'+pid+'/writers', headers=h, json={'recipient_subject':'alice','expires_at':expiry}).status_code == 404
    as_subject(peer)
    assert api.patch('/v1/properties/'+pid, headers=h, json={'label':'Reader rewrite','jurisdiction':'KA'}).status_code == 404
    assert api.get('/v1/properties/'+pid+'/writers', headers=h).status_code == 404
    as_subject('alice')
    assert api.request('DELETE', '/v1/properties/'+pid+'/writers', headers=h, json={'recipient_subject': editor}).json() == {'changed': True}
    as_subject(editor)
    assert api.patch('/v1/properties/'+pid, headers=h, json={'label':'After revoke','jurisdiction':'KA'}).status_code == 404
    assert api.post('/v1/properties/'+pid+'/claims', headers=h, json={'statement':'After revoke'}).status_code == 404


def test_expired_writer_and_cross_tenant_delegate_denied(api, private_record):
    from datetime import datetime, timedelta, timezone
    pid, peer, h, data, as_subject = private_record
    editor = _editor('temp-editor-'+str(uuid4()))
    expiry = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    assert api.put('/v1/properties/'+pid+'/writers', headers=h, json={'recipient_subject': editor, 'expires_at': expiry}).status_code == 200
    assert api.put('/v1/properties/'+pid+'/writers', headers={'X-Tenant-ID': str(B)}, json={'recipient_subject': editor, 'expires_at': expiry}).status_code == 403
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE property_write_grants SET expires_at=clock_timestamp()-interval '1 second' WHERE property_id=%s AND subject_id=%s", (pid, editor))
    as_subject(editor)
    assert api.patch('/v1/properties/'+pid, headers=h, json={'label':'Expired','jurisdiction':'KA'}).status_code == 404
    as_subject('alice')
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE tenant_memberships SET role='viewer' WHERE tenant_id=%s AND subject_id='alice'", (A,))
    try:
        assert api.patch('/v1/properties/'+pid, headers=h, json={'label':'Downgraded','jurisdiction':'KA'}).status_code == 403
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute("UPDATE tenant_memberships SET role='owner' WHERE tenant_id=%s AND subject_id='alice'", (A,))


def test_runtime_cannot_forge_corrections_or_write_grants(api, private_record):
    pid, peer, h, data, _ = private_record
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("INSERT INTO property_write_grants(tenant_id,property_id,subject_id,expires_at) VALUES(%s,%s,'alice',clock_timestamp()+interval '1 day')", (A, pid))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("INSERT INTO property_corrections(tenant_id,property_id,actor_subject,previous_label,previous_jurisdiction,label,jurisdiction) VALUES(%s,%s,'alice','a','KA','b','KA')", (A, pid))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("UPDATE properties SET label='forged' WHERE id=%s", (pid,))


def test_correction_failure_rolls_back_label(api, private_record):
    pid, peer, h, data, _ = private_record
    with psycopg.connect(DSN) as conn:
        conn.execute("ALTER TABLE property_audit_events ADD CONSTRAINT injected_correction_failure CHECK(event_type<>'property.corrected') NOT VALID")
    try:
        assert api.patch('/v1/properties/'+pid, headers=h, json={'label':'Must roll back','jurisdiction':'KA'}).status_code == 503
        assert api.get('/v1/properties/'+pid, headers=h).json()['label'] == 'Private record'
        with psycopg.connect(DSN) as conn:
            assert conn.execute('SELECT id FROM property_corrections WHERE property_id=%s', (pid,)).fetchall() == []
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('ALTER TABLE property_audit_events DROP CONSTRAINT injected_correction_failure')


def test_write_function_privileges():
    with psycopg.connect(DSN) as conn:
        for name in ('public.set_property_write_access(uuid,uuid,text,timestamptz)', 'public.correct_property(uuid,uuid,text,text)'):
            row = conn.execute("SELECT prosecdef,proconfig,NOT EXISTS(SELECT 1 FROM aclexplode(proacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE') FROM pg_proc WHERE oid=%s::regprocedure", (name,)).fetchone()
            assert row == (True, ['search_path=pg_catalog, pg_temp'], True)


def _correction_state(pid):
    with psycopg.connect(DSN) as conn:
        corrections = conn.execute('SELECT id FROM property_corrections WHERE property_id=%s', (pid,)).fetchall()
        audits = conn.execute("SELECT id FROM property_audit_events WHERE property_id=%s AND event_type='property.corrected'", (pid,)).fetchall()
    return corrections, audits


def test_correction_denies_nonmember_cross_tenant_reader_missing_mfa_and_revoked_grant(api, private_record):
    from datetime import datetime, timedelta, timezone
    from fastapi import HTTPException
    from app.main import app
    from app.auth import require_mfa
    pid, peer, h, data, as_subject = private_record
    body = {'label': 'Must not apply', 'jurisdiction': 'Bengaluru Rural'}
    original = api.get('/v1/properties/'+pid, headers=h).json()

    def unchanged():
        as_subject('alice')
        current = api.get('/v1/properties/'+pid, headers=h).json()
        assert current['label'] == original['label'] and current['jurisdiction'] == original['jurisdiction']
        assert _correction_state(pid) == ([], [])

    as_subject('nonmember-'+str(uuid4()))
    assert api.patch('/v1/properties/'+pid, headers=h, json=body).status_code == 403
    assert api.get('/v1/properties/'+pid+'/corrections', headers=h).status_code == 403
    unchanged()

    outsider = 'cross-'+str(uuid4())
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES(%s,%s,'owner')", (B, outsider))
    as_subject(outsider)
    assert api.patch('/v1/properties/'+pid, headers={'X-Tenant-ID': str(B)}, json=body).status_code == 404
    assert api.get('/v1/properties/'+pid+'/corrections', headers={'X-Tenant-ID': str(B)}).status_code == 404
    assert api.patch('/v1/properties/'+pid, headers=h, json=body).status_code == 403
    assert api.get('/v1/properties/'+pid+'/corrections', headers=h).status_code == 403
    as_subject('alice')
    assert api.patch('/v1/properties/'+pid, headers={'X-Tenant-ID': str(B)}, json=body).status_code == 403
    unchanged()

    as_subject(peer)
    assert api.patch('/v1/properties/'+pid, headers=h, json=body).status_code == 404
    assert api.get('/v1/properties/'+pid+'/corrections', headers=h).status_code == 404
    as_subject('alice')
    assert api.put('/v1/properties/'+pid+'/access', headers=h, json=data).status_code == 200
    as_subject(peer)
    assert api.get('/v1/properties/'+pid, headers=h).status_code == 200
    assert api.patch('/v1/properties/'+pid, headers=h, json=body).status_code == 404
    as_subject('alice')
    assert api.request('DELETE', '/v1/properties/'+pid+'/access', headers=h, json={'recipient_subject': peer}).json() == {'changed': True}
    as_subject(peer)
    assert api.patch('/v1/properties/'+pid, headers=h, json=body).status_code == 404
    assert api.get('/v1/properties/'+pid+'/corrections', headers=h).status_code == 404
    unchanged()

    other_owner = 'other-owner-'+str(uuid4())
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES(%s,%s,'owner')", (A, other_owner))
    as_subject(other_owner)
    assert api.patch('/v1/properties/'+pid, headers=h, json=body).status_code == 404
    unchanged()

    as_subject('alice')
    def denied():
        raise HTTPException(403, 'MFA access token required')
    app.dependency_overrides[require_mfa] = denied
    try:
        denied_response = api.patch('/v1/properties/'+pid, headers=h, json=body)
        assert denied_response.status_code == 403
    finally:
        app.dependency_overrides[require_mfa] = lambda: True
    unchanged()

    writer = _editor('revoked-writer-'+str(uuid4()))
    expiry = (datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    as_subject('alice')
    assert api.put('/v1/properties/'+pid+'/writers', headers=h, json={'recipient_subject': writer, 'expires_at': expiry}).json() == {'changed': True}
    assert api.request('DELETE', '/v1/properties/'+pid+'/writers', headers=h, json={'recipient_subject': writer}).json() == {'changed': True}
    as_subject(writer)
    assert api.patch('/v1/properties/'+pid, headers=h, json=body).status_code == 404
    assert api.get('/v1/properties/'+pid+'/corrections', headers=h).status_code == 404
    unchanged()

    as_subject('alice')
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE tenant_memberships SET role='viewer' WHERE tenant_id=%s AND subject_id='alice'", (A,))
    try:
        assert api.patch('/v1/properties/'+pid, headers=h, json=body).status_code == 403
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute("UPDATE tenant_memberships SET role='owner' WHERE tenant_id=%s AND subject_id='alice'", (A,))
    unchanged()


def test_editor_creator_corrects_label_or_jurisdiction(api, private_record):
    _, _, h, _, as_subject = private_record
    editor = _editor('creator-editor-'+str(uuid4()))
    as_subject(editor)
    created = api.post('/v1/properties', headers=h, json={'label': 'Editor plot', 'jurisdiction': 'KA'})
    assert created.status_code == 201, created.text
    pid = created.json()['id']
    label_only = api.patch('/v1/properties/'+pid, headers=h, json={'label': 'Editor plot renamed', 'jurisdiction': 'KA'})
    assert label_only.status_code == 200, label_only.text
    assert label_only.json()['changed'] is True and label_only.json()['jurisdiction'] == 'KA'
    place_only = api.patch('/v1/properties/'+pid, headers=h, json={'label': 'Editor plot renamed', 'jurisdiction': 'Bengaluru Urban'})
    assert place_only.status_code == 200, place_only.text
    assert place_only.json()['label'] == 'Editor plot renamed' and place_only.json()['jurisdiction'] == 'Bengaluru Urban'
    assert api.patch('/v1/properties/'+pid, headers=h, json={'label': 'Missing jurisdiction'}).status_code == 422
    history = api.get('/v1/properties/'+pid+'/corrections', headers=h).json()['items']
    pairs = {(item['previous_label'], item['label'], item['previous_jurisdiction'], item['jurisdiction']) for item in history}
    assert ('Editor plot', 'Editor plot renamed', 'KA', 'KA') in pairs
    assert ('Editor plot renamed', 'Editor plot renamed', 'KA', 'Bengaluru Urban') in pairs
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM property_audit_events WHERE property_id=%s AND event_type='property.corrected'", (pid,)).fetchone()[0] == 2


def test_correction_does_not_merge_conflicting_records(api, private_record):
    pid, _, h, _, _ = private_record
    claim = api.post('/v1/properties/'+pid+'/claims', headers=h, json={'statement': 'Stays on the first record'})
    assert claim.status_code == 201, claim.text
    claim_id = claim.json()['id']
    other = api.post('/v1/properties', headers=h, json={'label': 'Shared label', 'jurisdiction': 'Bengaluru Urban'})
    assert other.status_code == 201, other.text
    other_id = other.json()['id']
    assert api.patch('/v1/properties/'+pid, headers=h, json={'label': 'Shared label', 'jurisdiction': 'Bengaluru Urban', 'merge_with': other_id}).status_code == 422
    corrected = api.patch('/v1/properties/'+pid, headers=h, json={'label': 'Shared label', 'jurisdiction': 'Bengaluru Urban'})
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()['id'] == pid and corrected.json()['changed'] is True
    surviving = api.get('/v1/properties/'+other_id, headers=h).json()
    assert surviving['id'] == other_id and surviving['label'] == 'Shared label' and surviving['created_by'] == 'alice'
    assert api.get('/v1/properties/'+pid+'/claims', headers=h).json()['items'][0]['id'] == claim_id
    assert api.get('/v1/properties/'+other_id+'/claims', headers=h).json()['items'] == []
    assert api.get('/v1/properties/'+other_id+'/corrections', headers=h).json()['items'] == []
    assert len(api.get('/v1/properties/'+pid+'/corrections', headers=h).json()['items']) == 1
    with psycopg.connect(DSN) as conn:
        found = {row[0] for row in conn.execute('SELECT id::text FROM properties WHERE id IN (%s,%s)', (pid, other_id)).fetchall()}
        assert found == {pid, other_id}
        assert conn.execute('SELECT property_id::text FROM property_claims WHERE id=%s', (claim_id,)).fetchone()[0] == pid
        assert conn.execute("SELECT property_id::text FROM property_audit_events WHERE event_type='property.corrected' AND property_id IN (%s,%s)", (pid, other_id)).fetchall() == [(pid,)]


def _storage(monkeypatch):
    from base64 import urlsafe_b64encode
    monkeypatch.setenv('DOCUMENT_STORAGE_KEY', urlsafe_b64encode(b'A' * 32).decode())


def _pdf(marker=b'OYDP-SYNTHETIC-CLEAN'):
    return b'%PDF-1.4\n%' + marker + b'\n%%EOF'


def _png():
    return b'\x89PNG\r\n\x1a\n' + b'OYDP-SYNTHETIC-CLEAN'


def _upload(api, headers, property_id, body, media='application/pdf'):
    sent = dict(headers)
    sent['Content-Type'] = media
    return api.post(f'/v1/properties/{property_id}/documents', headers=sent, content=body)


def _docs(property_id):
    with psycopg.connect(DSN) as conn:
        return conn.execute('SELECT scan_state FROM property_documents WHERE property_id=%s ORDER BY created_at', (property_id,)).fetchall()


class _GateScanner:
    """Test double. It passes only generated bytes that carry the clean marker."""

    def scan(self, payload, media_type):
        if b'OYDP-SYNTHETIC-REJECT' in payload:
            return 'fail'
        if b'OYDP-SYNTHETIC-CLEAN' not in payload:
            return 'fail'
        return 'pass'


def _use_scanner():
    from app.documents import get_document_scanner
    from app.main import app
    app.dependency_overrides[get_document_scanner] = lambda: _GateScanner()


def test_oversize_document_is_not_stored(api, private_record, monkeypatch):
    from app.documents import MAX_UPLOAD_BYTES
    _storage(monkeypatch)
    pid, _, headers, _, _ = private_record
    body = b'%PDF-' + b'a' * MAX_UPLOAD_BYTES
    rejected = _upload(api, headers, pid, body)
    assert rejected.status_code == 413
    assert rejected.json()['detail'] == 'Document exceeds the size limit'
    assert body not in rejected.content
    assert _docs(pid) == []


def test_mismatched_document_content_is_not_stored(api, private_record, monkeypatch):
    _storage(monkeypatch)
    pid, _, headers, _, _ = private_record
    cases = [
        (_png(), 'application/pdf'),
        (_pdf(), 'image/png'),
        (_pdf(), 'image/jpeg'),
        (b'\x7fELF' + _pdf(), 'application/pdf'),
        (b'MZ' + _pdf(), 'application/pdf'),
        (b'<html>OYDP-SYNTHETIC-CLEAN</html>', 'application/pdf'),
        (_pdf(), 'application/pdf; charset=binary'),
        (b'', 'application/pdf'),
    ]
    for body, media in cases:
        rejected = _upload(api, headers, pid, body, media)
        assert rejected.status_code in (415, 422), rejected.text
        assert b'OYDP-SYNTHETIC' not in rejected.content
    assert _docs(pid) == []


def test_unauthorized_document_access_is_denied(api, private_record, monkeypatch):
    from uuid import uuid4
    from app.main import app
    from app.auth import require_mfa, verified_subject
    from fastapi import HTTPException
    _storage(monkeypatch)
    pid, peer, headers, data, as_subject = private_record
    uploaded = _upload(api, headers, pid, _pdf())
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()['scan_state'] == 'quarantined'
    assert 'ciphertext' not in uploaded.json()
    assert b'%PDF' not in uploaded.content
    document_id = uploaded.json()['id']
    content = f'/v1/properties/{pid}/documents/{document_id}/content'
    meta = f'/v1/properties/{pid}/documents/{document_id}'

    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    assert api.get(content, headers=headers).status_code == 503
    app.dependency_overrides.update(saved)

    as_subject('nonmember-' + str(uuid4()))
    assert _upload(api, headers, pid, _pdf()).status_code == 403
    assert api.get(content, headers=headers).status_code == 403

    outsider = 'cross-' + str(uuid4())
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,%s,'owner')", (B, outsider))
    as_subject(outsider)
    assert _upload(api, {'X-Tenant-ID': str(B)}, pid, _pdf()).status_code == 404
    assert api.get(content, headers={'X-Tenant-ID': str(B)}).status_code == 404
    assert api.get(meta, headers={'X-Tenant-ID': str(B)}).status_code == 404

    as_subject(peer)
    assert _upload(api, headers, pid, _pdf()).status_code == 404
    assert api.get(content, headers=headers).status_code == 404
    as_subject('alice')
    assert api.put(f'/v1/properties/{pid}/access', headers=headers, json=data).status_code == 200
    as_subject(peer)
    assert api.get(meta, headers=headers).status_code == 200
    assert _upload(api, headers, pid, _pdf()).status_code == 404
    denied = api.get(content, headers=headers)
    assert denied.status_code == 403
    assert b'OYDP-SYNTHETIC-CLEAN' not in denied.content

    def no_mfa():
        raise HTTPException(403, 'MFA access token required')
    as_subject('alice')
    app.dependency_overrides[require_mfa] = no_mfa
    try:
        assert _upload(api, headers, pid, _pdf()).status_code == 403
        assert api.get(content, headers=headers).status_code == 403
    finally:
        app.dependency_overrides[require_mfa] = lambda: True
        app.dependency_overrides[verified_subject] = lambda: 'alice'
    assert _docs(pid) == [('quarantined',)]


def test_revoked_document_access_is_denied(api, private_record, monkeypatch):
    from datetime import datetime, timedelta, timezone
    _storage(monkeypatch)
    _use_scanner()
    pid, _, headers, _, as_subject = private_record
    editor = _editor('doc-editor-' + str(uuid4()))
    expiry = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    grant = {'recipient_subject': editor, 'expires_at': expiry}
    assert api.put(f'/v1/properties/{pid}/access', headers=headers, json=grant).json() == {'changed': True}
    assert api.put(f'/v1/properties/{pid}/writers', headers=headers, json=grant).json() == {'changed': True}
    as_subject(editor)
    uploaded = _upload(api, headers, pid, _pdf())
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()['id']
    content = f'/v1/properties/{pid}/documents/{document_id}/content'
    meta = f'/v1/properties/{pid}/documents/{document_id}'
    blocked = api.get(content, headers=headers)
    assert blocked.status_code == 403
    assert b'OYDP-SYNTHETIC-CLEAN' not in blocked.content
    scanned = api.post(f'/v1/properties/{pid}/documents/{document_id}/scan', headers=headers)
    assert scanned.status_code == 200, scanned.text
    assert scanned.json()['scan_state'] == 'pass'
    released = api.get(content, headers=headers)
    assert released.status_code == 200
    assert released.content == _pdf()
    assert released.headers['content-disposition'] == 'attachment; filename="document"'
    as_subject('alice')
    assert api.request('DELETE', f'/v1/properties/{pid}/writers', headers=headers, json={'recipient_subject': editor}).json() == {'changed': True}
    as_subject(editor)
    assert _upload(api, headers, pid, _pdf()).status_code == 404
    assert api.get(content, headers=headers).status_code == 200
    as_subject('alice')
    assert api.request('DELETE', f'/v1/properties/{pid}/access', headers=headers, json={'recipient_subject': editor}).json() == {'changed': True}
    as_subject(editor)
    revoked = api.get(content, headers=headers)
    assert revoked.status_code == 404
    assert api.get(meta, headers=headers).status_code == 404
    assert b'OYDP-SYNTHETIC-CLEAN' not in revoked.content
    assert _docs(pid) == [('pass',)]


def test_scanner_absence_and_failed_scan_deny_download(api, private_record, monkeypatch):
    from app.documents import get_document_scanner
    from app.main import app
    _storage(monkeypatch)
    pid, _, headers, _, _ = private_record
    clean = _upload(api, headers, pid, _pdf())
    assert clean.status_code == 201, clean.text
    document_id = clean.json()['id']
    content = f'/v1/properties/{pid}/documents/{document_id}/content'
    forced = api.post(f'/v1/properties/{pid}/documents/{document_id}/scan', headers=headers, json={'scan_state': 'pass'})
    assert forced.status_code == 503
    assert forced.json()['detail'] == 'Document scanner unavailable'
    assert 'exploded' not in forced.text
    still = api.get(content, headers=headers)
    assert still.status_code == 403
    assert b'%PDF' not in still.content
    with psycopg.connect(DSN) as conn:
        digest = bytes(conn.execute('SELECT sha256 FROM property_documents WHERE id=%s', (document_id,)).fetchone()[0])
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), runtime(A) as conn:
        conn.execute('SELECT public.record_document_scan(%s,%s,%s,%s,%s)', (A, pid, document_id, 'pass', digest))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute('SELECT ciphertext,nonce FROM property_documents')
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("UPDATE property_documents SET scan_state='pass', scanned_at=clock_timestamp() WHERE id=%s", (document_id,))
    assert _docs(pid) == [('quarantined',)]

    rejected = _upload(api, headers, pid, _pdf(b'OYDP-SYNTHETIC-REJECT'))
    assert rejected.status_code == 201, rejected.text
    rejected_id = rejected.json()['id']
    app.dependency_overrides[get_document_scanner] = lambda: _GateScanner()
    decision = api.post(f'/v1/properties/{pid}/documents/{rejected_id}/scan', headers=headers)
    assert decision.status_code == 200, decision.text
    assert decision.json()['scan_state'] == 'fail'
    failed = api.get(f'/v1/properties/{pid}/documents/{rejected_id}/content', headers=headers)
    assert failed.status_code == 403
    assert b'OYDP-SYNTHETIC-REJECT' not in failed.content
    assert api.post(f'/v1/properties/{pid}/documents/{rejected_id}/scan', headers=headers).status_code == 409
    assert _docs(pid) == [('quarantined',), ('fail',)]


def test_unexpected_scanner_answer_does_not_release_bytes(api, private_record, monkeypatch):
    from app.documents import get_document_scanner
    from app.main import app
    _storage(monkeypatch)
    pid, _, headers, _, _ = private_record
    uploaded = _upload(api, headers, pid, _pdf())
    document_id = uploaded.json()['id']

    class _Odd:
        def scan(self, payload, media_type):
            return 'PASS'

    app.dependency_overrides[get_document_scanner] = lambda: _Odd()
    response = api.post(f'/v1/properties/{pid}/documents/{document_id}/scan', headers=headers)
    assert response.status_code == 503
    denied = api.get(f'/v1/properties/{pid}/documents/{document_id}/content', headers=headers)
    assert denied.status_code == 403
    assert denied.content != _pdf()
    assert _docs(pid) == [('quarantined',)]


def test_document_attribution_links_claim_source_and_identifier(api, private_record, monkeypatch):
    _storage(monkeypatch)
    pid, peer, headers, _, as_subject = private_record
    source = api.post('/v1/sources', headers=headers, json={
        'name': 'Survey sketch', 'origin': 'user_supplied', 'jurisdiction': 'Bengaluru Urban',
    })
    assert source.status_code == 201, source.text
    source_id = source.json()['id']
    claim = api.post(f'/v1/properties/{pid}/claims', headers=headers, json={
        'statement': 'Unverified boundary note', 'source_id': source_id,
    })
    assert claim.status_code == 201, claim.text
    claim_id = claim.json()['id']
    assert claim.json()['verification_status'] == 'unverified'
    identifier = api.post(
        f'/v1/properties/{pid}/identifiers',
        headers=headers,
        json={'scheme': 'survey', 'identifier_value': 'SY-ATTRIB-1'},
    )
    assert identifier.status_code == 200, identifier.text
    identifier_id = identifier.json()['id']
    assert identifier.json()['status'] == 'current'
    uploaded = _upload(api, headers, pid, _pdf())
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()['id']
    assert uploaded.json()['claim_id'] is None
    assert uploaded.json()['source_id'] is None
    assert uploaded.json()['identifier_id'] is None
    empty = api.put(
        f'/v1/properties/{pid}/documents/{document_id}/attribution',
        headers=headers,
        json={},
    )
    assert empty.status_code == 422 and empty.json()['detail'] == 'Invalid attribution'
    linked = api.put(
        f'/v1/properties/{pid}/documents/{document_id}/attribution',
        headers=headers,
        json={'claim_id': claim_id, 'source_id': source_id, 'identifier_id': identifier_id},
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body['claim_id'] == claim_id
    assert body['source_id'] == source_id
    assert body['identifier_id'] == identifier_id
    assert body['scan_state'] == 'quarantined'
    assert 'verification_status' not in body
    meta = api.get(f'/v1/properties/{pid}/documents/{document_id}', headers=headers).json()
    assert meta['claim_id'] == claim_id and meta['source_id'] == source_id
    assert meta['identifier_id'] == identifier_id
    assert api.post(
        f'/v1/properties/{pid}/consents', headers=headers, json={'purpose': 'passport_export'},
    ).status_code == 200
    packet = api.post(f'/v1/properties/{pid}/exports', headers=headers)
    assert packet.status_code == 200, packet.text
    exported = packet.json()
    assert exported['title_verified'] is False
    docs = exported['documents']
    assert len(docs) == 1
    assert docs[0]['claim_id'] == claim_id
    assert docs[0]['source_id'] == source_id
    assert docs[0]['identifier_id'] == identifier_id
    assert 'ciphertext' not in docs[0]
    foreign_claim = api.put(
        f'/v1/properties/{pid}/documents/{document_id}/attribution',
        headers=headers,
        json={'claim_id': str(uuid4())},
    )
    assert foreign_claim.status_code == 422 and foreign_claim.json()['detail'] == 'Invalid attribution'
    foreign_identifier = api.put(
        f'/v1/properties/{pid}/documents/{document_id}/attribution',
        headers=headers,
        json={'identifier_id': str(uuid4())},
    )
    assert foreign_identifier.status_code == 422 and foreign_identifier.json()['detail'] == 'Invalid attribution'
    superseded = api.post(
        f'/v1/properties/{pid}/identifiers',
        headers=headers,
        json={'scheme': 'survey', 'identifier_value': 'SY-ATTRIB-2', 'resolution': 'supersede'},
    )
    assert superseded.status_code == 200, superseded.text
    stale = api.put(
        f'/v1/properties/{pid}/documents/{document_id}/attribution',
        headers=headers,
        json={'identifier_id': identifier_id},
    )
    assert stale.status_code == 422 and stale.json()['detail'] == 'Invalid attribution'
    withdrawn = api.post(f'/v1/sources/{source_id}/withdrawal', headers=headers, json={'reason': 'Sketch replaced'})
    assert withdrawn.status_code == 200
    blocked = api.put(
        f'/v1/properties/{pid}/documents/{document_id}/attribution',
        headers=headers,
        json={'claim_id': claim_id, 'source_id': source_id},
    )
    assert blocked.status_code == 422 and blocked.json()['detail'] == 'Source is withdrawn'
    as_subject(peer)
    denied = api.put(
        f'/v1/properties/{pid}/documents/{document_id}/attribution',
        headers=headers,
        json={'claim_id': claim_id},
    )
    assert denied.status_code == 404
    as_subject('alice')
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A, 'alice') as conn:
        conn.execute(
            "UPDATE property_documents SET claim_id=%s, source_id=%s, identifier_id=%s WHERE id=%s",
            (claim_id, source_id, identifier_id, document_id),
        )


def test_missing_storage_key_does_not_store_plaintext(api, private_record, monkeypatch):
    monkeypatch.delenv('DOCUMENT_STORAGE_KEY', raising=False)
    pid, _, headers, _, _ = private_record
    rejected = _upload(api, headers, pid, _pdf())
    assert rejected.status_code == 503
    assert b'OYDP-SYNTHETIC-CLEAN' not in rejected.content
    assert _docs(pid) == []


def _trusted_privileges():
    functions = (
        'public.record_property_created_audit(uuid,uuid)',
        'public.record_document_quarantined_audit(uuid,uuid,uuid)',
        'public.record_diligence_audit(uuid,uuid,text)',
        'public.record_property_identifier(uuid,uuid,text,text,text)',
        'public.register_evidence_source(uuid,text,text,text)',
        'public.withdraw_evidence_source(uuid,uuid,text)',
        'public.record_professional_review(uuid,uuid,text,text,uuid,uuid,uuid,uuid)',
        'public.record_property_claim(uuid,uuid,text,uuid)',
        'public.attribute_property_document(uuid,uuid,uuid,uuid,uuid,uuid)',
        'public.record_property_consent(uuid,uuid,text)',
        'public.revoke_property_consent(uuid,uuid,text)',
        'public.authorize_property_export(uuid,uuid)',
    )
    hidden = (
        'public.actor_can_edit_property(uuid,uuid)',
        'public.ledger_row_must_match_outbox()',
        'public.copy_property_audit()',
        'public.copy_tenant_audit()',
        'public.reject_ledger_rewrite()',
    )
    tables = (
        'property_identifiers', 'evidence_sources', 'professional_reviews',
        'property_consents', 'tenant_audit_events', 'audit_ledger',
        'property_audit_events', 'evidence_assertions',
    )
    with psycopg.connect(DSN) as conn:
        for name in functions:
            row = conn.execute("""SELECT prosecdef, proconfig,
              has_function_privilege('oydp_app', %s::regprocedure, 'EXECUTE'),
              NOT EXISTS(SELECT 1 FROM aclexplode(proacl) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE')
              FROM pg_proc WHERE oid=%s::regprocedure""", (name, name)).fetchone()
            assert row == (True, ['search_path=pg_catalog, pg_temp'], True, True), name
        for name in hidden:
            assert conn.execute("SELECT has_function_privilege('oydp_app', %s::regprocedure, 'EXECUTE')", (name,)).fetchone()[0] is False
        for table in tables:
            assert conn.execute("SELECT has_table_privilege('oydp_app', %s, 'SELECT')", (table,)).fetchone()[0] is True
            for privilege in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                assert conn.execute("SELECT has_table_privilege('oydp_app', %s, %s)", (table, privilege)).fetchone()[0] is False


def test_identifier_history_is_idempotent_and_runtime_cannot_write_it(api, private_record):
    pid, _, headers, _, _ = private_record
    _trusted_privileges()
    url = f'/v1/properties/{pid}/identifiers'
    first = api.post(url, headers=headers, json={'scheme': 'survey', 'identifier_value': 'SY-1'})
    assert first.status_code == 200, first.text
    assert first.json()['version'] == 1 and first.json()['status'] == 'current' and first.json()['changed'] is True
    same = api.post(url, headers=headers, json={'scheme': 'survey', 'identifier_value': 'SY-1', 'resolution': 'supersede'})
    assert same.status_code == 200, same.text
    assert same.json()['changed'] is False and same.json()['id'] == first.json()['id'] and same.json()['version'] == 1
    replaced = api.post(url, headers=headers, json={'scheme': 'survey', 'identifier_value': 'SY-2', 'resolution': 'supersede'})
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()['status'] == 'current' and replaced.json()['version'] == 2 and replaced.json()['changed'] is True
    page = api.get(url, headers=headers).json()['items']
    current = [row for row in page if row['scheme'] == 'survey' and row['status'] == 'current']
    superseded = [row for row in page if row['scheme'] == 'survey' and row['status'] == 'superseded']
    assert len(current) == 1 and current[0]['identifier_value'] == 'SY-2'
    assert len(superseded) == 1 and superseded[0]['identifier_value'] == 'SY-1'
    missing = api.post(url, headers=headers, json={'scheme': 'survey', 'identifier_value': 'SY-3'})
    assert missing.status_code == 422 and missing.json()['detail'] == 'Identifier resolution required'
    assert 'SY-3' not in missing.text
    kept = [row for row in api.get(url, headers=headers).json()['items'] if row['status'] == 'current' and row['scheme'] == 'survey']
    assert len(kept) == 1 and kept[0]['identifier_value'] == 'SY-2'
    clash = api.post(url, headers=headers, json={'scheme': 'survey', 'identifier_value': 'SY-3', 'resolution': 'conflict'})
    assert clash.status_code == 200, clash.text
    assert clash.json()['status'] == 'conflict' and clash.json()['changed'] is True
    after = api.get(url, headers=headers).json()['items']
    current = [row for row in after if row['scheme'] == 'survey' and row['status'] == 'current']
    assert len(current) == 1 and current[0]['identifier_value'] == 'SY-2'
    assert api.get(f'/v1/properties/{uuid4()}/identifiers', headers=headers).status_code == 404
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("""INSERT INTO property_identifiers
          (tenant_id, property_id, scheme, identifier_value, version, status, recorded_by)
          VALUES (%s, %s, 'survey', 'FORGED', 9, 'current', 'alice')""", (A, pid))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("UPDATE property_identifiers SET identifier_value='FORGED' WHERE property_id=%s", (pid,))


def test_identifier_cross_tenant_is_hidden_and_reader_cannot_write(api, private_record):
    pid, peer, headers, data, as_subject = private_record
    url = f'/v1/properties/{pid}/identifiers'
    assert api.post(url, headers=headers, json={'scheme': 'khata', 'identifier_value': 'KH-1'}).status_code == 200
    as_subject('bob')
    assert api.get(url, headers={'X-Tenant-ID': str(B)}).status_code == 404
    assert api.post(url, headers={'X-Tenant-ID': str(B)}, json={'scheme': 'khata', 'identifier_value': 'KH-9'}).status_code == 404
    as_subject(peer)
    assert api.get(url, headers=headers).status_code == 404
    as_subject('alice')
    assert api.put(f'/v1/properties/{pid}/access', headers=headers, json=data).status_code == 200
    as_subject(peer)
    listed = api.get(url, headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()['items'][0]['identifier_value'] == 'KH-1'
    denied = api.post(url, headers=headers, json={'scheme': 'khata', 'identifier_value': 'KH-2', 'resolution': 'supersede'})
    assert denied.status_code == 404
    assert 'KH-2' not in denied.text
    as_subject('alice')
    assert [row for row in api.get(url, headers=headers).json()['items'] if row['status'] == 'current'][0]['identifier_value'] == 'KH-1'


def test_writer_can_record_identifier_and_review_without_verifying_a_claim(api, private_record, monkeypatch):
    from datetime import datetime, timedelta, timezone
    _storage(monkeypatch)
    pid, _, headers, _, as_subject = private_record
    claim = api.post(f'/v1/properties/{pid}/claims', headers=headers, json={'statement': 'Unverified boundary claim'})
    assert claim.status_code == 201 and claim.json()['verification_status'] == 'unverified'
    editor = _editor('evidence-editor-' + str(uuid4()))
    expiry = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    assert api.put(f'/v1/properties/{pid}/writers', headers=headers, json={'recipient_subject': editor, 'expires_at': expiry}).json() == {'changed': True}
    as_subject(editor)
    recorded = api.post(f'/v1/properties/{pid}/identifiers', headers=headers, json={'scheme': 'municipal', 'identifier_value': 'MUN-1'})
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()['recorded_by'] == editor and recorded.json()['status'] == 'current'
    identifier_id = recorded.json()['id']
    uploaded = _upload(api, headers, pid, _pdf())
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()['id']
    assert uploaded.json()['scan_state'] == 'quarantined'
    review = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'recorded',
        'statement': 'Noted from the file, not a title finding',
        'claim_id': claim.json()['id'],
        'document_id': document_id,
        'identifier_id': identifier_id,
    })
    assert review.status_code == 201, review.text
    body = review.json()
    assert body['title_effect'] == 'none' and body['disposition'] == 'recorded'
    assert body['claim_id'] == claim.json()['id']
    assert body['document_id'] == document_id
    assert body['identifier_id'] == identifier_id
    assert body['source_id'] is None
    listed = api.get(f'/v1/properties/{pid}/reviews', headers=headers).json()['items']
    assert listed and listed[0]['document_id'] == document_id and listed[0]['identifier_id'] == identifier_id
    foreign_document = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'recorded', 'statement': 'Unknown document citation', 'document_id': str(uuid4()),
    })
    assert foreign_document.status_code == 422 and foreign_document.json()['detail'] == 'Invalid attribution'
    foreign_identifier = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'recorded', 'statement': 'Unknown identifier citation', 'identifier_id': str(uuid4()),
    })
    assert foreign_identifier.status_code == 422 and foreign_identifier.json()['detail'] == 'Invalid attribution'
    superseded = api.post(
        f'/v1/properties/{pid}/identifiers',
        headers=headers,
        json={'scheme': 'municipal', 'identifier_value': 'MUN-2', 'resolution': 'supersede'},
    )
    assert superseded.status_code == 200, superseded.text
    stale = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'recorded', 'statement': 'Superseded identifier must fail', 'identifier_id': identifier_id,
    })
    assert stale.status_code == 422 and stale.json()['detail'] == 'Invalid attribution'
    claims = api.get(f'/v1/properties/{pid}/claims', headers=headers).json()['items']
    assert claims and all(item['verification_status'] == 'unverified' for item in claims)
    with psycopg.connect(DSN) as conn:
        assert conn.execute('SELECT DISTINCT verification_status FROM property_claims WHERE property_id=%s', (pid,)).fetchall() == [('unverified',)]
        row = conn.execute(
            'SELECT document_id::text, identifier_id::text FROM professional_reviews WHERE id=%s',
            (body['id'],),
        ).fetchone()
        assert row == (document_id, identifier_id)


@pytest.mark.parametrize('disposition', ['verified', 'title', 'official'])
def test_review_rejects_title_like_dispositions(api, private_record, disposition):
    pid, _, headers, _, _ = private_record
    response = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={'disposition': disposition, 'statement': 'Must not become title'})
    assert response.status_code == 422
    assert response.json()['detail'] == 'Invalid request'
    assert api.get(f'/v1/properties/{pid}/reviews', headers=headers).json()['items'] == []


def test_withdrawn_or_unknown_source_cannot_be_cited(api, private_record):
    pid, _, headers, _, _ = private_record
    forged = api.post('/v1/sources', headers=headers, json={
        'name': 'Field note', 'origin': 'user_supplied', 'jurisdiction': 'Bengaluru Urban', 'rights_status': 'owned',
    })
    assert forged.status_code == 422
    created = api.post('/v1/sources', headers=headers, json={
        'name': 'Field note', 'origin': 'user_supplied', 'jurisdiction': 'Bengaluru Urban',
    })
    assert created.status_code == 201, created.text
    assert created.json()['rights_status'] == 'unknown'
    source_id = created.json()['id']
    listed = api.get('/v1/sources', headers=headers).json()['items']
    assert listed[0]['id'] == source_id and listed[0]['rights_status'] == 'unknown'
    claim = api.post(f'/v1/properties/{pid}/claims', headers=headers, json={
        'statement': 'Unverified note linked to a live source', 'source_id': source_id,
    })
    assert claim.status_code == 201, claim.text
    assert claim.json()['verification_status'] == 'unverified'
    assert claim.json()['kind'] == 'user_claim'
    assert claim.json()['source_id'] == source_id
    cited = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'abstained', 'statement': 'The note was read and no conclusion was reached',
        'source_id': source_id, 'claim_id': claim.json()['id'],
    })
    assert cited.status_code == 201, cited.text
    assert cited.json()['title_effect'] == 'none'
    assert cited.json()['source_id'] == source_id
    assert cited.json()['claim_id'] == claim.json()['id']
    assert claim.json()['verification_status'] == 'unverified'
    unknown_review_claim = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'recorded', 'statement': 'Must reject a foreign claim citation', 'claim_id': str(uuid4()),
    })
    assert unknown_review_claim.status_code == 422 and unknown_review_claim.json()['detail'] == 'Invalid attribution'
    withdrawn = api.post(f'/v1/sources/{source_id}/withdrawal', headers=headers, json={'reason': 'The note was replaced'})
    assert withdrawn.status_code == 200 and withdrawn.json()['changed'] is True
    again = api.post(f'/v1/sources/{source_id}/withdrawal', headers=headers, json={'reason': 'The note was replaced'})
    assert again.json()['changed'] is False
    blocked_claim = api.post(f'/v1/properties/{pid}/claims', headers=headers, json={
        'statement': 'Must not cite a withdrawn source', 'source_id': source_id,
    })
    assert blocked_claim.status_code == 422 and blocked_claim.json()['detail'] == 'Source is withdrawn'
    blocked = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'recorded', 'statement': 'This citation must fail', 'source_id': source_id,
    })
    assert blocked.status_code == 422 and blocked.json()['detail'] == 'Source is withdrawn'
    unknown = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'recorded', 'statement': 'Missing source', 'source_id': str(uuid4()),
    })
    assert unknown.status_code == 422 and unknown.json()['detail'] == 'Source is withdrawn'
    unknown_claim = api.post(f'/v1/properties/{pid}/claims', headers=headers, json={
        'statement': 'Missing source claim', 'source_id': str(uuid4()),
    })
    assert unknown_claim.status_code == 422 and unknown_claim.json()['detail'] == 'Source is withdrawn'
    outsider = 'source-cross-' + str(uuid4())
    with pytest.raises(psycopg.Error), psycopg.connect(DSN) as conn:
        conn.execute("UPDATE evidence_sources SET rights_status='licensed' WHERE id=%s", (source_id,))
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s, %s, 'owner')", (B, outsider))
    from app.main import app
    from app.auth import verified_subject
    app.dependency_overrides[verified_subject] = lambda: outsider
    hidden = api.post(f'/v1/sources/{source_id}/withdrawal', headers={'X-Tenant-ID': str(B)}, json={'reason': 'Cross tenant'})
    assert hidden.status_code == 404
    assert api.get('/v1/sources', headers={'X-Tenant-ID': str(B)}).json()['items'] == []
    foreign_claim = api.post(
        f'/v1/properties/{pid}/claims',
        headers={'X-Tenant-ID': str(B)},
        json={'statement': 'Cross-tenant claim citation', 'source_id': source_id},
    )
    assert foreign_claim.status_code == 404


def test_evidence_conflicts_and_export_sources_stay_unverified(api, private_record, monkeypatch):
    _storage(monkeypatch)
    pid, peer, headers, _, as_subject = private_record
    quiet = api.get(f'/v1/properties/{pid}/evidence-conflicts', headers=headers)
    assert quiet.status_code == 200, quiet.text
    quiet_body = quiet.json()
    assert quiet_body['title_verified'] is False
    assert quiet_body['unresolved'] is False
    assert quiet_body['open_unverified_claim_count'] == 0
    assert quiet_body['multiple_open_unverified_claims'] is False
    assert quiet_body['identifier_conflicts'] == []
    assert quiet_body['claims_citing_withdrawn_sources'] == []
    source = api.post('/v1/sources', headers=headers, json={
        'name': 'Conflict note', 'origin': 'user_supplied', 'jurisdiction': 'Bengaluru Urban',
    })
    assert source.status_code == 201, source.text
    source_id = source.json()['id']
    first = api.post(f'/v1/properties/{pid}/claims', headers=headers, json={
        'statement': 'First unverified claim', 'source_id': source_id,
    })
    assert first.status_code == 201, first.text
    second = api.post(f'/v1/properties/{pid}/claims', headers=headers, json={
        'statement': 'Second unverified claim', 'source_id': source_id,
    })
    assert second.status_code == 201, second.text
    first_id, second_id = first.json()['id'], second.json()['id']
    conflicted = api.post(
        f'/v1/properties/{pid}/identifiers',
        headers=headers,
        json={'scheme': 'survey', 'identifier_value': 'CF-1'},
    )
    assert conflicted.status_code == 200, conflicted.text
    conflict_mark = api.post(
        f'/v1/properties/{pid}/identifiers',
        headers=headers,
        json={'scheme': 'survey', 'identifier_value': 'CF-2', 'resolution': 'conflict'},
    )
    assert conflict_mark.status_code == 200, conflict_mark.text
    assert conflict_mark.json()['status'] == 'conflict'
    withdrawn = api.post(f'/v1/sources/{source_id}/withdrawal', headers=headers, json={'reason': 'Replaced note'})
    assert withdrawn.status_code == 200
    signals = api.get(f'/v1/properties/{pid}/evidence-conflicts', headers=headers)
    assert signals.status_code == 200, signals.text
    body = signals.json()
    assert body['title_verified'] is False
    assert body['unresolved'] is True
    assert body['multiple_open_unverified_claims'] is True
    assert body['open_unverified_claim_count'] == 2
    assert set(body['open_unverified_claim_ids']) == {first_id, second_id}
    assert len(body['identifier_conflicts']) == 1
    assert body['identifier_conflicts'][0]['status'] == 'conflict'
    assert set(body['claims_citing_withdrawn_sources']) == {first_id, second_id}
    assert 'First unverified claim' not in signals.text
    assert 'Second unverified claim' not in signals.text
    assert all('statement' not in row for row in body['identifier_conflicts'])
    assert api.post(f'/v1/properties/{pid}/consents', headers=headers, json={'purpose': 'passport_export'}).status_code == 200
    packet = api.post(f'/v1/properties/{pid}/exports', headers=headers)
    assert packet.status_code == 200, packet.text
    exported = packet.json()
    assert exported['title_verified'] is False
    assert 'sources' in exported
    assert len(exported['sources']) == 1
    assert exported['sources'][0]['id'] == source_id
    assert exported['sources'][0]['rights_status'] == 'unknown'
    assert exported['sources'][0]['withdrawn_at'] is not None
    as_subject(peer)
    denied = api.get(f'/v1/properties/{pid}/evidence-conflicts', headers=headers)
    assert denied.status_code == 404
    assert first_id not in denied.text
    as_subject('alice')
    from app.main import app
    from app.auth import verified_subject
    app.dependency_overrides.pop(verified_subject, None)
    unauth = api.get(f'/v1/properties/{pid}/evidence-conflicts', headers=headers)
    assert unauth.status_code in (401, 503)
    app.dependency_overrides[verified_subject] = lambda: 'alice'


def test_evidence_graph_projects_attribution_edges_without_title(api, private_record, monkeypatch):
    _storage(monkeypatch)
    pid, peer, headers, _, as_subject = private_record
    empty = api.get(f'/v1/properties/{pid}/evidence-graph', headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json() == {
        'property_id': pid,
        'title_verified': False,
        'notice': (
            'Evidence graph projection only. Not a title certificate; claims remain unverified; '
            'reviews are not title; document citations do not change scan state.'
        ),
        'edges': [],
    }
    source = api.post('/v1/sources', headers=headers, json={
        'name': 'Graph note', 'origin': 'user_supplied', 'jurisdiction': 'Bengaluru Urban',
    })
    assert source.status_code == 201, source.text
    source_id = source.json()['id']
    claim = api.post(f'/v1/properties/{pid}/claims', headers=headers, json={
        'statement': 'Unverified graph claim', 'source_id': source_id,
    })
    assert claim.status_code == 201, claim.text
    claim_id = claim.json()['id']
    identifier = api.post(
        f'/v1/properties/{pid}/identifiers',
        headers=headers,
        json={'scheme': 'survey', 'identifier_value': 'GRAPH-1'},
    )
    assert identifier.status_code == 200, identifier.text
    identifier_id = identifier.json()['id']
    uploaded = _upload(api, headers, pid, _pdf())
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()['id']
    linked = api.put(
        f'/v1/properties/{pid}/documents/{document_id}/attribution',
        headers=headers,
        json={'claim_id': claim_id, 'source_id': source_id, 'identifier_id': identifier_id},
    )
    assert linked.status_code == 200, linked.text
    review = api.post(f'/v1/properties/{pid}/reviews', headers=headers, json={
        'disposition': 'recorded',
        'statement': 'Graph review citation, not title',
        'claim_id': claim_id,
        'document_id': document_id,
        'identifier_id': identifier_id,
        'source_id': source_id,
    })
    assert review.status_code == 201, review.text
    review_id = review.json()['id']
    graph = api.get(f'/v1/properties/{pid}/evidence-graph', headers=headers)
    assert graph.status_code == 200, graph.text
    body = graph.json()
    assert body['title_verified'] is False
    assert 'Evidence graph projection only' in body['notice']
    assert 'ciphertext' not in graph.text and 'SELECT' not in graph.text
    edge_set = {
        (e['from_kind'], e['from_id'], e['to_kind'], e['to_id'], e['relation'])
        for e in body['edges']
    }
    assert ('claim', claim_id, 'source', source_id, 'cites_source') in edge_set
    assert ('document', document_id, 'claim', claim_id, 'attributed_to_claim') in edge_set
    assert ('document', document_id, 'source', source_id, 'attributed_to_source') in edge_set
    assert ('document', document_id, 'identifier', identifier_id, 'attributed_to_identifier') in edge_set
    assert ('review', review_id, 'claim', claim_id, 'cites_claim') in edge_set
    assert ('review', review_id, 'document', document_id, 'cites_document') in edge_set
    assert ('review', review_id, 'identifier', identifier_id, 'cites_identifier') in edge_set
    assert ('review', review_id, 'source', source_id, 'cites_source') in edge_set
    as_subject(peer)
    denied = api.get(f'/v1/properties/{pid}/evidence-graph', headers=headers)
    assert denied.status_code == 404
    assert 'Unverified graph claim' not in denied.text
    as_subject('alice')
    from app.main import app
    from app.auth import verified_subject
    app.dependency_overrides.pop(verified_subject, None)
    unauth = api.get(f'/v1/properties/{pid}/evidence-graph', headers=headers)
    assert unauth.status_code in (401, 503)
    assert 'Unverified graph claim' not in unauth.text
    app.dependency_overrides[verified_subject] = lambda: 'alice'


def test_export_requires_live_creator_consent_and_stays_unverified(api, private_record, monkeypatch):
    _storage(monkeypatch)
    pid, _, headers, _, _ = private_record
    secret = 'Claim text that must stay out of a refused export'
    assert api.post(f'/v1/properties/{pid}/claims', headers=headers, json={'statement': secret}).status_code == 201
    assert api.post(f'/v1/properties/{pid}/identifiers', headers=headers, json={'scheme': 'internal', 'identifier_value': 'INT-1'}).status_code == 200
    refused = api.post(f'/v1/properties/{pid}/exports', headers=headers)
    assert refused.status_code == 403 and refused.json()['detail'] == 'Export consent required'
    assert secret not in refused.text and 'ciphertext' not in refused.text and 'SELECT' not in refused.text
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT 1 FROM property_audit_events WHERE property_id=%s AND event_type='packet.exported'", (pid,)).fetchall() == []
    consent = api.post(f'/v1/properties/{pid}/consents', headers=headers, json={'purpose': 'passport_export'})
    assert consent.status_code == 200, consent.text
    assert consent.json()['changed'] is True and consent.json()['purpose'] == 'passport_export'
    assert api.post(f'/v1/properties/{pid}/consents', headers=headers, json={'purpose': 'passport_export'}).json()['changed'] is False
    uploaded = _upload(api, headers, pid, _pdf())
    assert uploaded.status_code == 201, uploaded.text
    packet = api.post(f'/v1/properties/{pid}/exports', headers=headers)
    assert packet.status_code == 200, packet.text
    body = packet.json()
    assert body['title_verified'] is False
    assert 'not a title certificate' in body['notice']
    assert body['claims'][0]['statement'] == secret and body['claims'][0]['verification_status'] == 'unverified'
    assert body['identifiers'][0]['identifier_value'] == 'INT-1'
    assert body['documents'][0]['scan_state'] == 'quarantined'
    assert 'ciphertext' not in packet.text and 'nonce' not in packet.text and b'%PDF' not in packet.content
    listed = api.get(f'/v1/properties/{pid}/documents', headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()['items'][0]['scan_state'] == 'quarantined'
    assert 'ciphertext' not in listed.text and 'nonce' not in listed.text and b'%PDF' not in listed.content
    audit = api.get(f'/v1/properties/{pid}/audit', headers=headers)
    assert audit.status_code == 200, audit.text
    exported = [row for row in audit.json()['items'] if row['event_type'] == 'packet.exported']
    assert exported and set(exported[0]) == {'event_type', 'actor_subject', 'recorded_at', 'delivered_at'}
    assert api.request('DELETE', f'/v1/properties/{pid}/consents', headers=headers, json={'purpose': 'passport_export'}).json() == {'changed': True}
    blocked = api.post(f'/v1/properties/{pid}/exports', headers=headers)
    assert blocked.status_code == 403 and blocked.json()['detail'] == 'Export consent required'
    assert secret not in blocked.text
    with psycopg.connect(DSN) as conn:
        assert len(conn.execute("SELECT 1 FROM property_audit_events WHERE property_id=%s AND event_type='packet.exported'", (pid,)).fetchall()) == 1


def test_delegated_writer_cannot_consent_or_export(api, private_record):
    from datetime import datetime, timedelta, timezone
    pid, peer, headers, data, as_subject = private_record
    secret = 'Delegated writer must not receive this claim'
    assert api.post(f'/v1/properties/{pid}/claims', headers=headers, json={'statement': secret}).status_code == 201
    editor = _editor('consent-editor-' + str(uuid4()))
    expiry = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    grant = {'recipient_subject': editor, 'expires_at': expiry}
    assert api.put(f'/v1/properties/{pid}/writers', headers=headers, json=grant).json() == {'changed': True}
    as_subject(editor)
    consent = api.post(f'/v1/properties/{pid}/consents', headers=headers, json={'purpose': 'passport_export'})
    export = api.post(f'/v1/properties/{pid}/exports', headers=headers)
    assert consent.status_code == 404 and export.status_code == 404
    assert secret not in consent.text and secret not in export.text
    as_subject('alice')
    assert api.put(f'/v1/properties/{pid}/access', headers=headers, json=data).status_code == 200
    as_subject(peer)
    assert api.post(f'/v1/properties/{pid}/consents', headers=headers, json={'purpose': 'passport_export'}).status_code == 404
    assert api.post(f'/v1/properties/{pid}/exports', headers=headers).status_code == 404
    as_subject('alice')
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT 1 FROM property_consents WHERE property_id=%s", (pid,)).fetchall() == []


def test_ledger_row_follows_property_create_and_rejects_rewrite(api, private_record):
    pid, _, headers, _, _ = private_record
    with psycopg.connect(DSN) as conn:
        delivered = conn.execute("""SELECT event_type, actor_subject FROM audit_ledger
          WHERE property_id=%s AND event_type='property.created'""", (pid,)).fetchall()
        before = conn.execute('SELECT count(*) FROM audit_ledger').fetchone()[0]
    assert delivered == [('property.created', 'alice')]
    audit = api.get(f'/v1/properties/{pid}/audit', headers=headers)
    assert audit.status_code == 200, audit.text
    created = [row for row in audit.json()['items'] if row['event_type'] == 'property.created']
    assert created and set(created[0]) == {'event_type', 'actor_subject', 'recorded_at', 'delivered_at'}
    assert created[0]['actor_subject'] == 'alice'
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute("UPDATE audit_ledger SET event_type='forged' WHERE property_id=%s", (pid,))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime(A) as conn:
        conn.execute('DELETE FROM audit_ledger WHERE property_id=%s', (pid,))
    with pytest.raises(psycopg.Error), runtime(A) as conn:
        conn.execute('TRUNCATE audit_ledger')
    for statement in (
        "UPDATE audit_ledger SET event_type='forged'",
        'DELETE FROM audit_ledger',
        'TRUNCATE audit_ledger',
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='append-only'), psycopg.connect(DSN) as conn:
            conn.execute(statement)
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='append-only'), psycopg.connect(DSN) as conn:
        conn.execute("""INSERT INTO audit_ledger
          (source_event_id, source_table, tenant_id, property_id, actor_subject, event_type, recorded_at)
          VALUES (%s, 'property_audit_events', %s, %s, 'alice', 'property.created', clock_timestamp())""",
                     (uuid4(), A, pid))
    with psycopg.connect(DSN) as conn:
        assert conn.execute('SELECT count(*) FROM audit_ledger').fetchone()[0] == before
    as_other = 'audit-cross-' + str(uuid4())
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s, %s, 'owner')", (B, as_other))
    from app.main import app
    from app.auth import verified_subject
    app.dependency_overrides[verified_subject] = lambda: as_other
    assert api.get(f'/v1/properties/{pid}/audit', headers={'X-Tenant-ID': str(B)}).status_code == 404
    assert api.get(f'/v1/properties/{pid}/documents', headers={'X-Tenant-ID': str(B)}).status_code == 404
