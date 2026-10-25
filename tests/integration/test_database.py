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
        conn.execute('INSERT INTO properties(id,tenant_id,label,jurisdiction) VALUES (%s,%s,\'A\',\'KA\'),(%s,%s,\'B\',\'KA\')', (PA,A,PB,B))
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
    from app.auth import verified_subject
    monkeypatch.setenv('DATABASE_URL', make_conninfo(DSN, user='oydp_app', password=PASSWORD))
    # Cryptographic validation has separate RSA tests. These exercise the real API,
    # trusted membership lookup and PostgreSQL RLS using an injected verified subject.
    app.dependency_overrides[verified_subject] = lambda: 'alice'
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
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'alice','viewer')", (B,))
    headers = {'X-Tenant-ID':str(B)}
    assert api.get('/v1/properties/'+str(PB), headers=headers).status_code == 200
    with psycopg.connect(DSN) as conn:
        conn.execute("DELETE FROM tenant_memberships WHERE tenant_id=%s AND subject_id='alice'", (B,))
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
    token = jwt.encode(dict(iss='https://id.example.test',aud='oydp-api',sub='alice',iat=now,exp=now+300), key,
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
