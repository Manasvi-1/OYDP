"""Document upload/scan/content MFA gates with real require_mfa.

Upload resolves MFA before any writer/DB work. Scan and content stub authorized_db
only so DATABASE_URL is not required. Synthetic JWKS tokens are not live IdP evidence.
Never force scan_state=pass in these negatives.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth import jwks_client
from app.main import app, authorized_db

PDF = b'%PDF-1.4\n%OYDP-SYNTHETIC-CLEAN\n'


@pytest.fixture
def doc_mfa_client(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv('OIDC_ISSUER', 'https://identity.example.test')
    monkeypatch.setenv('OIDC_AUDIENCE', 'oydp-api')
    monkeypatch.setenv('OIDC_JWKS_URL', 'https://identity.example.test/keys')
    monkeypatch.delenv('OYDP_OIDC_DEV_HTTP', raising=False)
    monkeypatch.delenv('OYDP_MFA_MAX_AGE_SECONDS', raising=False)
    client_keys = Mock()
    client_keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    monkeypatch.setattr('app.auth.jwks_client', lambda _: client_keys)
    now = int(datetime.now(timezone.utc).timestamp())

    def token(**changes):
        claims = {
            'iss': 'https://identity.example.test',
            'aud': 'oydp-api',
            'sub': 'alice',
            'iat': now,
            'exp': now + 300,
        }
        claims.update(changes)
        return jwt.encode(claims, key, algorithm='RS256', headers={'kid': 'test', 'typ': 'at+jwt'})

    def fake_authorized_db(tenant_id=None, subject: str = 'alice'):
        yield SimpleNamespace(execute=Mock()), 'owner'

    app.dependency_overrides[authorized_db] = fake_authorized_db
    try:
        yield TestClient(app), token, now
    finally:
        app.dependency_overrides.clear()
        jwks_client.cache_clear()


def _ids():
    return str(uuid4()), str(uuid4()), str(uuid4())


def test_document_upload_rejects_password_only_amr(doc_mfa_client):
    client, token, now = doc_mfa_client
    property_id, _document_id, tenant_id = _ids()
    response = client.post(
        f'/v1/properties/{property_id}/documents',
        headers={
            'Authorization': f'Bearer {token(amr=["pwd"], auth_time=now)}',
            'X-Tenant-ID': tenant_id,
            'Content-Type': 'application/pdf',
        },
        content=PDF,
    )
    assert response.status_code == 403
    assert response.json()['detail'] == 'MFA access token required'
    assert PDF not in response.content


def test_document_upload_rejects_missing_auth_time(doc_mfa_client):
    client, token, _now = doc_mfa_client
    property_id, _document_id, tenant_id = _ids()
    response = client.post(
        f'/v1/properties/{property_id}/documents',
        headers={
            'Authorization': f'Bearer {token(amr=["pwd", "otp"])}',
            'X-Tenant-ID': tenant_id,
            'Content-Type': 'application/pdf',
        },
        content=PDF,
    )
    assert response.status_code == 403
    assert response.json()['detail'] == 'Fresh MFA authentication required'
    assert PDF not in response.content


def test_document_scan_rejects_stale_auth_time(doc_mfa_client, monkeypatch):
    client, token, now = doc_mfa_client
    monkeypatch.setenv('OYDP_MFA_MAX_AGE_SECONDS', '60')
    property_id, document_id, tenant_id = _ids()
    response = client.post(
        f'/v1/properties/{property_id}/documents/{document_id}/scan',
        headers={
            'Authorization': f'Bearer {token(amr=["pwd", "otp"], auth_time=now - 61)}',
            'X-Tenant-ID': tenant_id,
        },
    )
    assert response.status_code == 403
    assert response.json()['detail'] == 'Fresh MFA authentication required'


def test_document_content_rejects_password_only_amr(doc_mfa_client):
    client, token, now = doc_mfa_client
    property_id, document_id, tenant_id = _ids()
    response = client.get(
        f'/v1/properties/{property_id}/documents/{document_id}/content',
        headers={
            'Authorization': f'Bearer {token(amr=["pwd"], auth_time=now)}',
            'X-Tenant-ID': tenant_id,
        },
    )
    assert response.status_code == 403
    assert response.json()['detail'] == 'MFA access token required'
    assert PDF not in response.content


def test_document_content_rejects_zero_mfa_max_age_outside_loopback(doc_mfa_client, monkeypatch):
    client, token, now = doc_mfa_client
    monkeypatch.delenv('OYDP_OIDC_DEV_HTTP', raising=False)
    monkeypatch.setenv('OYDP_MFA_MAX_AGE_SECONDS', '0')
    property_id, document_id, tenant_id = _ids()
    response = client.get(
        f'/v1/properties/{property_id}/documents/{document_id}/content',
        headers={
            'Authorization': f'Bearer {token(amr=["pwd", "mfa"], auth_time=now)}',
            'X-Tenant-ID': tenant_id,
        },
    )
    assert response.status_code == 503
    assert response.json()['detail'] == 'Invalid MFA freshness configuration'
    assert PDF not in response.content
