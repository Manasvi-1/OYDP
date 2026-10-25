"""Disposable DB only. Native CI uses a real restricted login; embedded mode uses SET ROLE."""
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import pytest
import psycopg
from fastapi.testclient import TestClient
from oydp.api import create_app, PropertyInput, ClaimInput, AccessInput
from oydp.auth import Identity
from oydp.repository import Repository, Unavailable, InvalidAccess
from test_api import keys, token, verifier

ADMIN = os.environ.get('OYDP_TEST_ADMIN_DSN')
RUNTIME = os.environ.get('OYDP_TEST_RUNTIME_DSN')
EMBEDDED = os.environ.get('OYDP_TEST_EMBEDDED') == '1'
pytestmark = pytest.mark.skipif(not ADMIN or not RUNTIME, reason='Disposable PostgreSQL DSNs not configured')
CONNECT = psycopg.connect
ROOT = Path(__file__).resolve().parents[1]


def connect_for_tests(*args, **kwargs):
    # PGlite socket detach can race the next sequential client handshake.
    # Retry only connection establishment in embedded tests, never SQL or assertions.
    for attempt in range(5 if EMBEDDED else 1):
        try:
            return CONNECT(*args, **kwargs)
        except psycopg.OperationalError:
            if not EMBEDDED or attempt == 4:
                raise
            time.sleep(0.05)


def admin():
    c=connect_for_tests(ADMIN, autocommit=True)
    c.execute('RESET ROLE')
    return c


@pytest.fixture(scope='module', autouse=True)
def schema():
    if not ADMIN or not RUNTIME: yield; return
    if os.environ.get('OYDP_TEST_ALLOW_RESET') != 'yes':
        raise RuntimeError('Explicit disposable-database acknowledgement required')
    with admin() as c:
        assert c.execute("SELECT to_regnamespace('oydp')").fetchone()[0] is None, 'Use an empty disposable DB'
        if EMBEDDED:
            c.execute('CREATE ROLE oydp_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS')
        c.execute((ROOT/'migrations/001_foundation.up.sql').read_text())
        c.execute((ROOT/'migrations/002_property_access.up.sql').read_text())
        c.execute((ROOT/'migrations/002_property_access.down.sql').read_text())
        c.execute((ROOT/'migrations/002_property_access.up.sql').read_text())
    yield
    with admin() as c:
        c.execute((ROOT/'migrations/001_foundation.down.sql').read_text())
        assert c.execute("SELECT to_regnamespace('oydp')").fetchone()[0] is None
        c.execute((ROOT/'migrations/001_foundation.up.sql').read_text())
        c.execute((ROOT/'migrations/001_foundation.down.sql').read_text())


@pytest.fixture
def setup_db(monkeypatch):
    tenant, other, subject, peer = [uuid4() for _ in range(4)]
    with admin() as c:
        for t,s in [(tenant,subject),(tenant,peer),(other,peer)]:
            c.execute('INSERT INTO oydp.memberships VALUES(%s,%s,true)',(t,s))
    if EMBEDDED:
        def restricted_connect(*args,**kwargs):
            c=connect_for_tests(*args,**kwargs)
            c.execute('SET ROLE oydp_runtime')
            c.commit()
            return c
        monkeypatch.setattr(psycopg,'connect',restricted_connect)
    repo=Repository(RUNTIME)
    actor=Identity(subject,True)
    return repo,tenant,other,actor,Identity(peer,True)


def test_persist_and_read_across_connections(setup_db):
    repo,t,_,a,_=setup_db
    p=repo.create(t,a,PropertyInput(name='Candidate'))
    assert repo.get(t,a,p['id'])['jurisdiction']=='unresolved'
    assert repo.list(t,a,25,0)[0]['id']==p['id']
    assert Repository(RUNTIME).get(t,a,p['id'])['name']=='Candidate'


def test_create_and_claim_audited_atomically(setup_db):
    repo,t,_,a,_=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    claim=repo.claim(t,a,p['id'],ClaimInput(statement='Applicant claim'))
    assert claim['kind']=='user_claim'
    with admin() as c:
        events=c.execute('SELECT event_type FROM oydp.audit_outbox WHERE tenant_id=%s ORDER BY occurred_at',(t,)).fetchall()
        assert events==[('property.created',),('claim.recorded',)]


def test_same_tenant_without_grant_denied(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    assert repo.list(t,peer,25,0)==[]
    with pytest.raises(Unavailable): repo.get(t,peer,p['id'])
    with pytest.raises(Unavailable): repo.claim(t,peer,p['id'],ClaimInput(statement='No grant'))


def test_cross_tenant_denied(setup_db):
    repo,t,other,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with pytest.raises(Unavailable): repo.get(other,peer,p['id'])
    with pytest.raises(Unavailable): repo.create(other,a,PropertyInput(name='Forged tenant'))


def test_membership_revocation(setup_db):
    repo,t,_,a,_=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with admin() as c:
        c.execute('UPDATE oydp.memberships SET active=false WHERE tenant_id=%s',(t,))
    with pytest.raises(Unavailable): repo.get(t,a,p['id'])


@pytest.mark.parametrize('change',["revoked=true", "expires_at=clock_timestamp()-interval '1 second'"])
def test_grant_revocation_and_expiry(setup_db,change):
    repo,t,_,a,_=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with admin() as c:
        c.execute('UPDATE oydp.grants SET '+change+' WHERE tenant_id=%s',(t,))
    with pytest.raises(Unavailable): repo.get(t,a,p['id'])
    assert repo.list(t,a,25,0)==[]


def test_audit_failure_rolls_back_property_and_grants(setup_db, monkeypatch):
    repo,t,_,a,_=setup_db
    def fail(*args): raise RuntimeError('Simulated sink insert failure')
    monkeypatch.setattr(repo,'audit',fail)
    with pytest.raises(RuntimeError): repo.create(t,a,PropertyInput(name='Rollback'))
    with admin() as c:
        for table in ('properties','grants','audit_outbox'):
            assert c.execute(f'SELECT count(*) FROM oydp.{table} WHERE tenant_id=%s',(t,)).fetchone()[0]==0


def test_rls_cross_tenant_and_missing_context(setup_db):
    repo,t,other,a,_=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with psycopg.connect(RUNTIME) as c:
        assert c.execute('SELECT count(*) FROM oydp.properties').fetchone()[0]==0
        c.execute("SELECT set_config('oydp.tenant_id',%s,true),set_config('oydp.subject_id',%s,true)",(str(other),str(a.subject)))
        assert c.execute('SELECT count(*) FROM oydp.properties').fetchone()[0]==0
    with repo.transaction(t,a) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('INSERT INTO oydp.properties(tenant_id,id,created_by,name,jurisdiction) VALUES(%s,%s,%s,%s,%s)',
                      (other,uuid4(),a.subject,'bad','unknown'))


def test_context_does_not_survive_commit(setup_db):
    repo,t,_,a,_=setup_db
    repo.create(t,a,PropertyInput(name='Private'))
    with psycopg.connect(RUNTIME) as c:
        c.execute("SELECT set_config('oydp.tenant_id',%s,true),set_config('oydp.subject_id',%s,true)",(str(t),str(a.subject)))
        assert c.execute('SELECT count(*) FROM oydp.properties').fetchone()[0]==1
        c.commit()
        assert c.execute('SELECT count(*) FROM oydp.properties').fetchone()[0]==0


def test_database_rejects_claim_promotion_and_audit_edit(setup_db):
    repo,t,_,a,_=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with repo.transaction(t,a) as c:
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute('INSERT INTO oydp.claims VALUES(%s,%s,%s,%s,%s,%s,clock_timestamp())',
                      (t,p['id'],uuid4(),a.subject,'Forged','verified'))
    with repo.transaction(t,a) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('DELETE FROM oydp.audit_outbox WHERE tenant_id=%s',(t,))


def test_http_to_database(keys,setup_db):
    repo,t,other,a,peer=setup_db
    client=TestClient(create_app(repo,verifier(keys)))
    h={'Authorization':'Bearer '+token(keys,a.subject),'X-Tenant-ID':str(t)}
    r=client.post('/v1/properties',headers=h,json={'name':'HTTP candidate'})
    assert r.status_code==201,r.text
    pid=r.json()['id']
    assert client.get('/v1/properties/'+pid,headers=h).status_code==200
    r=client.post('/v1/properties/'+pid+'/claims',headers=h,json={'statement':'Unverified'})
    assert r.status_code==201 and r.json()['kind']=='user_claim'
    assert client.get('/v1/properties/'+pid,headers={**h,'X-Tenant-ID':str(other)}).status_code==404


def test_runtime_cannot_reassign_membership_or_grant(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with repo.transaction(t,a) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('UPDATE oydp.memberships SET subject_id=subject_id WHERE tenant_id=%s',(t,))
    with repo.transaction(t,a) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('UPDATE oydp.grants SET subject_id=%s WHERE tenant_id=%s',(peer.subject,t))


def test_foreign_key_rejects_cross_tenant_property_claim(setup_db):
    repo,t,other,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with repo.transaction(other,peer) as c:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            c.execute('INSERT INTO oydp.claims(tenant_id,property_id,id,created_by,statement) VALUES(%s,%s,%s,%s,%s)',
                      (other,p['id'],uuid4(),peer.subject,'Cross-tenant'))


@pytest.mark.skipif(EMBEDDED, reason='Requires native PostgreSQL concurrent connections')
@pytest.mark.parametrize('target', ['membership', 'grant'])
def test_revocation_serializes_with_active_transaction(setup_db, target):
    repo,t,_,a,_=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with repo.transaction(t,a) as conn:
        if target == 'grant':
            repo.check_grant(conn,t,a.subject,p['id'],'property:read')
        with admin() as revoker:
            revoker.execute("SET lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                if target == 'membership':
                    revoker.execute('UPDATE oydp.memberships SET active=false WHERE tenant_id=%s AND subject_id=%s',(t,a.subject))
                else:
                    revoker.execute("UPDATE oydp.grants SET revoked=true WHERE tenant_id=%s AND subject_id=%s AND action='property:read'",(t,a.subject))
    with admin() as revoker:
        if target == 'membership':
            revoker.execute('UPDATE oydp.memberships SET active=false WHERE tenant_id=%s AND subject_id=%s',(t,a.subject))
        else:
            revoker.execute("UPDATE oydp.grants SET revoked=true WHERE tenant_id=%s AND subject_id=%s AND action='property:read'",(t,a.subject))
    with pytest.raises(Unavailable):
        repo.get(t,a,p['id'])


def access_input(*actions, days=1):
    return AccessInput(actions=set(actions or ['property:read']),
                       expires_at=datetime.now(timezone.utc)+timedelta(days=days))


def test_share_read_downgrade_and_revoke(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Sharing'))
    repo.claim(t,a,p['id'],ClaimInput(statement='An unverified claim'))
    assert repo.access(t,a,p['id'],peer.subject,access_input()) == {'changed':True}
    assert repo.get(t,peer,p['id'])['name']=='Sharing'
    assert repo.claims(t,peer,p['id'],25,0)[0]['kind']=='user_claim'
    with pytest.raises(Unavailable): repo.claim(t,peer,p['id'],ClaimInput(statement='Denied'))
    repo.access(t,a,p['id'],peer.subject,access_input('property:read','property:write'))
    repo.claim(t,peer,p['id'],ClaimInput(statement='Collaborator claim'))
    repo.access(t,a,p['id'],peer.subject,access_input())
    with pytest.raises(Unavailable): repo.claim(t,peer,p['id'],ClaimInput(statement='Downgraded'))
    assert repo.access(t,a,p['id'],peer.subject)=={'changed':True}
    assert repo.list(t,peer,25,0)==[]
    with pytest.raises(Unavailable): repo.claims(t,peer,p['id'],25,0)
    with pytest.raises(Unavailable): repo.get(t,peer,p['id'])


def test_access_idempotence_and_audit_details(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Sharing'))
    data=access_input()
    repo.access(t,a,p['id'],peer.subject,data)
    assert repo.access(t,a,p['id'],peer.subject,data)=={'changed':False}
    repo.access(t,a,p['id'],peer.subject)
    assert repo.access(t,a,p['id'],peer.subject)=={'changed':False}
    with admin() as c:
        rows=c.execute('''SELECT event_type,target_subject_id,granted_actions,access_expires_at
            FROM oydp.audit_outbox WHERE tenant_id=%s AND target_subject_id IS NOT NULL ORDER BY occurred_at''',(t,)).fetchall()
    assert rows==[('access.changed',peer.subject,['property:read'],data.expires_at),
                  ('access.revoked',peer.subject,[],None)]


def test_writer_cannot_reshare_or_revoke(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    repo.access(t,a,p['id'],peer.subject,access_input('property:read','property:write'))
    with pytest.raises(Unavailable): repo.access(t,peer,p['id'],a.subject,access_input())
    with pytest.raises(Unavailable): repo.access(t,peer,p['id'],a.subject)
    assert repo.get(t,a,p['id'])


@pytest.mark.parametrize('case',['self','missing','inactive','different_tenant','wrong_property','missing_mfa'])
def test_invalid_access_targets(setup_db,case):
    repo,t,other,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    target=peer.subject
    if case=='self': target=a.subject
    if case=='missing': target=uuid4()
    if case=='missing_mfa': a=Identity(a.subject,False)
    if case=='wrong_property': p['id']=uuid4()
    with admin() as c:
        if case=='inactive': c.execute('UPDATE oydp.memberships SET active=false WHERE tenant_id=%s AND subject_id=%s',(t,target))
        if case=='different_tenant':
            target=uuid4()
            c.execute('INSERT INTO oydp.memberships VALUES(%s,%s,true)',(other,target))
    with pytest.raises(Unavailable): repo.access(t,a,p['id'],target,access_input())


@pytest.mark.parametrize('days',[-1,31])
def test_expiry_policy(setup_db,days):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with pytest.raises(InvalidAccess): repo.access(t,a,p['id'],peer.subject,access_input(days=days))


def test_write_only_access_denied(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with pytest.raises(InvalidAccess):
        repo.access(t,a,p['id'],peer.subject,access_input('property:write'))


def test_expired_controller_cannot_share(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with admin() as c:
        c.execute("UPDATE oydp.grants SET expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id=%s",(t,))
    with pytest.raises(Unavailable): repo.access(t,a,p['id'],peer.subject,access_input())


def test_revocation_for_inactive_recipient_still_works(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    repo.access(t,a,p['id'],peer.subject,access_input())
    with admin() as c:
        c.execute('UPDATE oydp.memberships SET active=false WHERE tenant_id=%s AND subject_id=%s',(t,peer.subject))
    assert repo.access(t,a,p['id'],peer.subject)=={'changed':True}


def test_access_audit_failure_rolls_back_grants(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with admin() as c:
        c.execute("ALTER TABLE oydp.audit_outbox ADD CONSTRAINT injected_failure CHECK(event_type NOT IN ('access.changed','access.revoked')) NOT VALID")
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            repo.access(t,a,p['id'],peer.subject,access_input())
        assert repo.list(t,peer,25,0)==[]
    finally:
        with admin() as c: c.execute('ALTER TABLE oydp.audit_outbox DROP CONSTRAINT injected_failure')


def test_sharing_http_journey(keys,setup_db):
    repo,t,_,a,peer=setup_db
    client=TestClient(create_app(repo,verifier(keys)))
    owner={'Authorization':'Bearer '+token(keys,a.subject),'X-Tenant-ID':str(t)}
    guest={'Authorization':'Bearer '+token(keys,peer.subject),'X-Tenant-ID':str(t)}
    p=client.post('/v1/properties',headers=owner,json={'name':'Shared record'}).json()['id']
    url=f'/v1/properties/{p}/access/{peer.subject}'
    r=client.put(url,headers=owner,json=access_input().model_dump(mode='json'))
    assert r.status_code==200 and r.json()=={'changed':True}
    assert client.get(f'/v1/properties/{p}',headers=guest).status_code==200
    assert client.get(f'/v1/properties/{p}/claims',headers=guest).json()==[]
    assert client.delete(url,headers=owner).status_code==200
    assert client.get(f'/v1/properties/{p}',headers=guest).status_code==404


def test_runtime_cannot_insert_another_members_grant(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with repo.transaction(t,peer) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("INSERT INTO oydp.grants VALUES(%s,%s,%s,'property:read',clock_timestamp()+interval '1 day',false)",
                      (t,p['id'],peer.subject))


def test_delegation_cannot_outlive_controller(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    with admin() as c:
        c.execute("UPDATE oydp.grants SET expires_at=clock_timestamp()+interval '1 hour' WHERE tenant_id=%s",(t,))
    with pytest.raises(InvalidAccess): repo.access(t,a,p['id'],peer.subject,access_input())


def test_access_rollback_preserves_audit_history(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Private'))
    repo.access(t,a,p['id'],peer.subject,access_input())
    with admin() as c:
        with pytest.raises(psycopg.errors.RaiseException):
            c.execute((ROOT/'migrations/002_property_access.down.sql').read_text())
        c.execute('ROLLBACK')
    assert repo.get(t,peer,p['id'])


def test_access_function_not_executable_by_public(setup_db):
    with admin() as c:
        row=c.execute("""SELECT prosecdef,proconfig,
          NOT EXISTS(SELECT 1 FROM aclexplode(proacl) acl WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE')
          FROM pg_proc WHERE oid='oydp.set_property_access(uuid,uuid,uuid,text[],timestamptz)'::regprocedure""").fetchone()
    assert row==(True,['search_path=pg_catalog, pg_temp'],True)


@pytest.mark.skipif(EMBEDDED, reason='Requires native PostgreSQL concurrent connections')
def test_shared_access_revocation_waits_for_active_reader(setup_db):
    repo,t,_,a,peer=setup_db
    p=repo.create(t,a,PropertyInput(name='Concurrent sharing'))
    repo.access(t,a,p['id'],peer.subject,access_input())
    with repo.transaction(t,peer) as reader:
        repo.check_grant(reader,t,peer.subject,p['id'],'property:read')
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with repo.transaction(t,a) as revoker:
                revoker.execute("SET LOCAL lock_timeout='100ms'")
                revoker.execute('SELECT oydp.set_property_access(%s,%s,%s,%s,%s)',
                                (t,p['id'],peer.subject,[],None))
    assert repo.get(t,peer,p['id'])
    assert repo.access(t,a,p['id'],peer.subject)=={'changed':True}
    with pytest.raises(Unavailable): repo.get(t,peer,p['id'])
