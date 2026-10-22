"""Disposable DB only. Native CI uses a real restricted login; embedded mode uses SET ROLE."""
import os
import time
from pathlib import Path
from uuid import uuid4
import pytest
import psycopg
from fastapi.testclient import TestClient
from oydp.api import create_app, PropertyInput, ClaimInput
from oydp.auth import Identity
from oydp.repository import Repository, Unavailable
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
