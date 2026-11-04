"""Transactional audit outbox against disposable PostgreSQL."""
import json
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from scripts.deliver_audit import deliver
from scripts.migrate import migrate, provision_runtime

DSN = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DSN, reason='TEST_DATABASE_URL is required for real PostgreSQL tests')
PASSWORD = 'synthetic-test-only-password-32-chars'


@pytest.fixture(scope='module', autouse=True)
def database():
    migrate(DSN)
    provision_runtime(DSN, PASSWORD)
    yield
    with psycopg.connect(DSN) as conn:
        conn.execute("DELETE FROM audit_outbox WHERE event_id IN (SELECT id FROM property_audit_events WHERE actor_subject LIKE 'audit-%')")
        conn.execute("DELETE FROM property_audit_events WHERE actor_subject LIKE 'audit-%'")
        conn.execute("DELETE FROM properties WHERE created_by LIKE 'audit-%'")
        conn.execute("DELETE FROM tenant_memberships WHERE subject_id LIKE 'audit-%'")


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from app.auth import require_mfa, verified_subject
    from app.main import app
    monkeypatch.setenv('DATABASE_URL', make_conninfo(DSN, user='oydp_app', password=PASSWORD))
    app.dependency_overrides[verified_subject] = lambda: 'audit-alice'
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_event_and_outbox_commit_and_deliver_once(api, tmp_path):
    tenant = uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'audit-alice','owner')", (tenant,))
    created = api.post('/v1/properties', headers={'X-Tenant-ID': str(tenant)}, json={'label': 'Audited candidate', 'jurisdiction': 'Bengaluru Urban'})
    assert created.status_code == 201, created.text
    property_id = created.json()['id']
    pending = api.get(f'/v1/properties/{property_id}/audit', headers={'X-Tenant-ID': str(tenant)})
    assert pending.status_code == 200, pending.text
    assert pending.json()['items'][0]['event_type'] == 'property.created'
    assert pending.json()['items'][0]['delivered_at'] is not None
    with psycopg.connect(DSN) as conn:
        queued = conn.execute('SELECT delivered_at FROM audit_outbox WHERE property_id=%s', (property_id,)).fetchone()
    assert queued is not None and queued[0] is None
    sink = tmp_path / 'audit.jsonl'
    for _ in range(20):
        if deliver(DSN, sink, limit=1000) == 0:
            break
    lines = [json.loads(line) for line in sink.read_text().splitlines()]
    matched = [line for line in lines if line['property_id'] == property_id]
    assert matched and matched[0]['event_type'] == 'property.created'
    assert 'statement' not in matched[0]
    with psycopg.connect(DSN) as conn:
        marked = conn.execute('SELECT delivered_at FROM audit_outbox WHERE property_id=%s', (property_id,)).fetchone()
    assert marked is not None and marked[0] is not None
    again = tmp_path / 'again.jsonl'
    before = sink.read_text().count(property_id)
    assert deliver(DSN, again) == 0 or property_id not in again.read_text()
    assert sink.read_text().count(property_id) == before
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE audit_outbox SET event_type='tampered' WHERE property_id=%s", (property_id,))


def test_failed_property_does_not_enqueue(api):
    tenant = uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'audit-alice','owner')", (tenant,))
        before = conn.execute('SELECT count(*) FROM audit_outbox').fetchone()[0]
        conn.execute('REVOKE INSERT ON property_audit_events FROM oydp_app')
    try:
        failed = api.post('/v1/properties', headers={'X-Tenant-ID': str(tenant)}, json={'label': 'Must not land', 'jurisdiction': 'KA'})
        assert failed.status_code == 503
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('GRANT INSERT ON property_audit_events TO oydp_app')
            assert conn.execute('SELECT count(*) FROM audit_outbox').fetchone()[0] == before
            assert conn.execute("SELECT id FROM properties WHERE label='Must not land'").fetchone() is None


def test_other_tenant_cannot_read_audit(api):
    tenant = uuid4()
    other = uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'audit-alice','owner'),(%s,'audit-mallory','owner')", (tenant, other))
    created = api.post('/v1/properties', headers={'X-Tenant-ID': str(tenant)}, json={'label': 'Hidden audit', 'jurisdiction': 'KA'})
    property_id = created.json()['id']
    from app.auth import verified_subject
    from app.main import app
    app.dependency_overrides[verified_subject] = lambda: 'audit-mallory'
    assert api.get(f'/v1/properties/{property_id}/audit', headers={'X-Tenant-ID': str(other)}).status_code == 404
