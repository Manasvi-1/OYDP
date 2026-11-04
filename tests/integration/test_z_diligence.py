"""Diligence requests against disposable PostgreSQL."""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from fastapi import HTTPException
from psycopg.conninfo import make_conninfo

from scripts.migrate import migrate, provision_runtime

DSN = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DSN, reason='TEST_DATABASE_URL is required for real PostgreSQL tests')
PASSWORD = 'synthetic-test-only-password-32-chars'


@pytest.fixture(scope='module', autouse=True)
def database():
    migrate(DSN)
    provision_runtime(DSN, PASSWORD)


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from app.auth import require_mfa, verified_subject
    from app.main import app
    monkeypatch.setenv('DATABASE_URL', make_conninfo(DSN, user='oydp_app', password=PASSWORD))
    app.dependency_overrides[verified_subject] = lambda: 'diligence-alice'
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_creator_opens_note_and_close_and_reader_can_note(api):
    from app.auth import verified_subject
    from app.main import app
    tenant = uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'diligence-alice','owner'),(%s,'diligence-peer','viewer')", (tenant, tenant))
    headers = {'X-Tenant-ID': str(tenant)}
    created = api.post('/v1/properties', headers=headers, json={'label': 'Diligence candidate', 'jurisdiction': 'Bengaluru Rural'})
    assert created.status_code == 201, created.text
    property_id = created.json()['id']
    opened = api.post(f'/v1/properties/{property_id}/requests', headers=headers, json={'title': 'Ask for the packet', 'body': 'Please list the papers you hold.'})
    assert opened.status_code == 201, opened.text
    request_id = opened.json()['id']
    assert opened.json()['status'] == 'open' and opened.json()['closed_at'] is None
    expiry = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    shared = api.put(f'/v1/properties/{property_id}/access', headers=headers, json={'recipient_subject': 'diligence-peer', 'expires_at': expiry})
    assert shared.status_code == 200, shared.text
    app.dependency_overrides[verified_subject] = lambda: 'diligence-peer'
    assert api.post(f'/v1/properties/{property_id}/requests', headers=headers, json={'title': 'no', 'body': 'no'}).status_code == 404
    noted = api.post(f'/v1/properties/{property_id}/requests/{request_id}/notes', headers=headers, json={'body': 'I can read the request and add a note.'})
    assert noted.status_code == 201, noted.text
    assert noted.json()['created_by'] == 'diligence-peer'
    assert api.post(f'/v1/properties/{property_id}/requests/{request_id}/close', headers=headers).status_code == 404
    app.dependency_overrides[verified_subject] = lambda: 'diligence-alice'
    closed = api.post(f'/v1/properties/{property_id}/requests/{request_id}/close', headers=headers)
    assert closed.status_code == 200, closed.text
    assert closed.json()['status'] == 'closed' and closed.json()['closed_at']
    late = api.post(f'/v1/properties/{property_id}/requests/{request_id}/notes', headers=headers, json={'body': 'too late'})
    assert late.status_code == 404
    notes = api.get(f'/v1/properties/{property_id}/requests/{request_id}/notes', headers=headers)
    assert notes.status_code == 200 and notes.json()['items'][0]['body'].startswith('I can read')


def test_other_tenant_and_missing_mfa_are_denied(api):
    from app.auth import require_mfa, verified_subject
    from app.main import app
    tenant, other = uuid4(), uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'diligence-alice','owner'),(%s,'diligence-mallory','owner')", (tenant, other))
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = api.post('/v1/properties', headers=headers, json={'label': 'Private request', 'jurisdiction': 'KA'}).json()['id']
    app.dependency_overrides[verified_subject] = lambda: 'diligence-mallory'
    assert api.get(f'/v1/properties/{property_id}/requests', headers={'X-Tenant-ID': str(other)}).status_code == 404
    app.dependency_overrides[verified_subject] = lambda: 'diligence-alice'
    app.dependency_overrides[require_mfa] = lambda: (_ for _ in ()).throw(HTTPException(403, 'MFA access token required'))
    assert api.post(f'/v1/properties/{property_id}/requests', headers=headers, json={'title': 'blocked', 'body': 'blocked'}).status_code == 403


def test_request_audit_failure_rolls_back(api):
    tenant = uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'diligence-alice','owner')", (tenant,))
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = api.post('/v1/properties', headers=headers, json={'label': 'Rollback request', 'jurisdiction': 'KA'}).json()['id']
    with psycopg.connect(DSN) as conn:
        conn.execute('REVOKE INSERT ON property_audit_events FROM oydp_app')
    try:
        failed = api.post(f'/v1/properties/{property_id}/requests', headers=headers, json={'title': 'lost', 'body': 'lost'})
        assert failed.status_code == 503
        listed = api.get(f'/v1/properties/{property_id}/requests', headers=headers)
        assert listed.status_code == 200 and listed.json()['items'] == []
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('GRANT INSERT ON property_audit_events TO oydp_app')
