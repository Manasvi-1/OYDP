"""Private document gate against disposable PostgreSQL."""
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from scripts.migrate import migrate, provision_runtime

DSN = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DSN, reason='TEST_DATABASE_URL is required for real PostgreSQL tests')
PASSWORD = 'synthetic-test-only-password-32-chars'
PNG = b'\x89PNG\r\n\x1a\n' + b'png-body'
ACTIVE = b'%PDF-1.4\n/JavaScript (alert)\n%%EOF'


@pytest.fixture(scope='module', autouse=True)
def database(tmp_path_factory):
    migrate(DSN)
    provision_runtime(DSN, PASSWORD)
    storage = tmp_path_factory.mktemp('documents')
    os.environ['DOCUMENT_STORAGE_DIR'] = str(storage)
    os.environ['DOCUMENT_ENCRYPTION_KEY'] = '11' * 32
    yield storage
    with psycopg.connect(DSN) as conn:
        conn.execute("DELETE FROM property_audit_events WHERE actor_subject LIKE 'docs-%'")
        conn.execute("DELETE FROM property_documents WHERE created_by LIKE 'docs-%'")
        conn.execute("DELETE FROM properties WHERE created_by LIKE 'docs-%'")
        conn.execute("DELETE FROM tenant_memberships WHERE subject_id LIKE 'docs-%'")


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from app.auth import require_mfa, verified_subject
    from app.main import app
    monkeypatch.setenv('DATABASE_URL', make_conninfo(DSN, user='oydp_app', password=PASSWORD))
    monkeypatch.setenv('DOCUMENT_STORAGE_DIR', os.environ['DOCUMENT_STORAGE_DIR'])
    monkeypatch.setenv('DOCUMENT_ENCRYPTION_KEY', os.environ['DOCUMENT_ENCRYPTION_KEY'])
    app.dependency_overrides[verified_subject] = lambda: 'docs-alice'
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def workspace(subject='docs-alice', role='owner'):
    tenant = uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute('INSERT INTO tenant_memberships VALUES (%s,%s,%s)', (tenant, subject, role))
    return tenant


def create_property(api, tenant):
    response = api.post('/v1/properties', headers={'X-Tenant-ID': str(tenant)}, json={'label': 'Document candidate', 'jurisdiction': 'Hyderabad'})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_clean_png_is_encrypted_and_downloadable(api, database):
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    stored = api.post(f'/v1/properties/{property_id}/documents', headers=headers, content=PNG)
    assert stored.status_code == 201, stored.text
    body = stored.json()
    assert body['status'] == 'clean' and body['media_type'] == 'image/png' and body['rejection_code'] is None
    saved = list((database / str(tenant)).iterdir())
    assert saved and saved[0].read_bytes() != PNG
    downloaded = api.get(f'/v1/properties/{property_id}/documents/{body["id"]}', headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content == PNG
    assert downloaded.headers['content-type'].startswith('image/png')
    assert 'attachment' in downloaded.headers['content-disposition']
    assert downloaded.headers['x-content-type-options'] == 'nosniff'


def test_active_pdf_is_rejected_without_bytes(api, database):
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    rejected = api.post(f'/v1/properties/{property_id}/documents', headers=headers, content=ACTIVE)
    assert rejected.status_code == 201, rejected.text
    assert rejected.json()['status'] == 'rejected' and rejected.json()['rejection_code'] == 'active'
    assert api.get(f'/v1/properties/{property_id}/documents/{rejected.json()["id"]}', headers=headers).status_code == 404
    assert not (database / str(tenant)).exists() or not any((database / str(tenant)).iterdir())


def test_other_member_and_missing_mfa_cannot_use_documents(api):
    from fastapi import HTTPException
    from app.auth import require_mfa
    from app.main import app
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    stored = api.post(f'/v1/properties/{property_id}/documents', headers=headers, content=PNG)
    assert stored.status_code == 201, stored.text
    other = workspace(subject='docs-mallory')
    app.dependency_overrides[__import__('app.auth', fromlist=['verified_subject']).verified_subject] = lambda: 'docs-mallory'
    assert api.get(f'/v1/properties/{property_id}/documents', headers={'X-Tenant-ID': str(other)}).status_code == 404
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,'docs-peer','owner')", (tenant,))
    app.dependency_overrides[__import__('app.auth', fromlist=['verified_subject']).verified_subject] = lambda: 'docs-peer'
    assert api.get(f'/v1/properties/{property_id}/documents/{stored.json()["id"]}', headers=headers).status_code == 404
    app.dependency_overrides[__import__('app.auth', fromlist=['verified_subject']).verified_subject] = lambda: 'docs-alice'
    app.dependency_overrides[require_mfa] = lambda: (_ for _ in ()).throw(HTTPException(403, 'MFA access token required'))
    assert api.post(f'/v1/properties/{property_id}/documents', headers=headers, content=PNG).status_code == 403


def test_audit_failure_removes_ciphertext(api, database):
    tenant = workspace()
    headers = {'X-Tenant-ID': str(tenant)}
    property_id = create_property(api, tenant)
    with psycopg.connect(DSN) as conn:
        conn.execute('REVOKE INSERT ON property_audit_events FROM oydp_app')
    try:
        failed = api.post(f'/v1/properties/{property_id}/documents', headers=headers, content=PNG)
        assert failed.status_code == 503
        listed = api.get(f'/v1/properties/{property_id}/documents', headers=headers)
        assert listed.status_code == 200 and listed.json()['items'] == []
        assert not (database / str(tenant)).exists() or not any((database / str(tenant)).iterdir())
    finally:
        with psycopg.connect(DSN) as conn:
            conn.execute('GRANT INSERT ON property_audit_events TO oydp_app')
