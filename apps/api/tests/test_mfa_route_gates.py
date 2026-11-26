"""HTTP route MFA gates with real require_mfa (no MFA dependency override).

authorized_db is stubbed only so DATABASE_URL is not required. Tokens are
synthetic JWKS-signed access tokens; this is not live IdP enrollment evidence.
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


@pytest.fixture
def mfa_client(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv('OIDC_ISSUER', 'https://identity.example.test')
    monkeypatch.setenv('OIDC_AUDIENCE', 'oydp-api')
    monkeypatch.setenv('OIDC_JWKS_URL', 'https://identity.example.test/keys')
    monkeypatch.delenv('OYDP_OIDC_DEV_HTTP', raising=False)
    monkeypatch.delenv('OYDP_MFA_MAX_AGE_SECONDS', raising=False)
    monkeypatch.delenv('OYDP_MFA_ACR_VALUES', raising=False)
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


def _headers(token: str):
    return {
        'Authorization': f'Bearer {token}',
        'X-Tenant-ID': str(uuid4()),
    }


@pytest.mark.parametrize(
    'method,path,kwargs',
    [
        ('post', '/v1/properties', {'json': {'label': 'Gate', 'jurisdiction': 'KA'}}),
        (
            'put',
            '/v1/properties/{pid}/access',
            {
                'json': {
                    'recipient_subject': 'bob',
                    'expires_at': '2099-01-01T00:00:00+00:00',
                }
            },
        ),
        (
            'post',
            '/v1/properties/{pid}/claims',
            {'json': {'statement': 'synthetic claim text'}},
        ),
        ('post', '/v1/properties/{pid}/exports', {}),
        (
            'post',
            '/v1/properties/{pid}/requests',
            {'json': {'title': 'Diligence gate', 'body': 'Need source pack'}},
        ),
        (
            'put',
            '/v1/properties/{pid}/documents/{did}/attribution',
            {'json': {'claim_id': str(uuid4())}},
        ),
        (
            'post',
            '/v1/properties/{pid}/evidence-conflict-dispositions',
            {
                'json': {
                    'signal_kind': 'identifier_conflict',
                    'signal_id': str(uuid4()),
                    'outcome': 'noted',
                    'reason': 'MFA gate must reject password-only tokens',
                }
            },
        ),
        ('post', '/v1/tenant/membership-revocations', {'json': {'subject_id': 'bob'}}),
        ('post', '/v1/tenant/session-invalidations', {'json': {'subject_id': 'bob'}}),
    ],
)
def test_high_risk_routes_reject_password_only_amr(mfa_client, method, path, kwargs):
    client, token, now = mfa_client
    pid = str(uuid4())
    target = path.format(pid=pid, did=str(uuid4()))
    response = getattr(client, method)(
        target,
        headers=_headers(token(amr=['pwd'], auth_time=now)),
        **kwargs,
    )
    assert response.status_code == 403
    assert response.json()['detail'] == 'MFA access token required'


@pytest.mark.parametrize(
    'method,path,kwargs',
    [
        ('post', '/v1/properties', {'json': {'label': 'Gate', 'jurisdiction': 'KA'}}),
        (
            'put',
            '/v1/properties/{pid}/access',
            {
                'json': {
                    'recipient_subject': 'bob',
                    'expires_at': '2099-01-01T00:00:00+00:00',
                }
            },
        ),
        ('post', '/v1/properties/{pid}/exports', {}),
    ],
)
def test_high_risk_routes_reject_missing_auth_time(mfa_client, method, path, kwargs):
    client, token, _now = mfa_client
    pid = str(uuid4())
    target = path.format(pid=pid)
    response = getattr(client, method)(
        target,
        headers=_headers(token(amr=['pwd', 'otp'])),
        **kwargs,
    )
    assert response.status_code == 403
    assert response.json()['detail'] == 'Fresh MFA authentication required'


def test_high_risk_routes_reject_stale_auth_time(mfa_client, monkeypatch):
    client, token, now = mfa_client
    monkeypatch.setenv('OYDP_MFA_MAX_AGE_SECONDS', '60')
    pid = str(uuid4())
    response = client.post(
        f'/v1/properties/{pid}/claims',
        headers=_headers(token(amr=['pwd', 'otp'], auth_time=now - 61)),
        json={'statement': 'stale auth_time must not write'},
    )
    assert response.status_code == 403
    assert response.json()['detail'] == 'Fresh MFA authentication required'


def test_export_rejects_zero_mfa_max_age_outside_loopback_dev(mfa_client, monkeypatch):
    client, token, now = mfa_client
    monkeypatch.delenv('OYDP_OIDC_DEV_HTTP', raising=False)
    monkeypatch.setenv('OYDP_MFA_MAX_AGE_SECONDS', '0')
    pid = str(uuid4())
    response = client.post(
        f'/v1/properties/{pid}/exports',
        headers=_headers(token(amr=['pwd', 'mfa'], auth_time=now)),
    )
    assert response.status_code == 503
    assert response.json()['detail'] == 'Invalid MFA freshness configuration'
