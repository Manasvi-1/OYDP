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
        assert migrate(upgrade)==['006_private_property_access.sql','007_attributed_claims.sql','008_evidence_lineage.sql','009_private_documents.sql','010_audit_outbox.sql','011_diligence_requests.sql']
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
    with pytest.raises(psycopg.errors.CheckViolation), runtime(tenant,owner) as conn:
        conn.execute("INSERT INTO property_claims(tenant_id,property_id,statement,kind) VALUES(%s,%s,'Not official','official_observation')",(tenant,pid))


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
