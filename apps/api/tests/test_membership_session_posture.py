"""Unit coverage for membership-revoke session posture (no live IdP)."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app, enforce_membership_session


client = TestClient(app)


def test_membership_revoke_fails_closed_without_oidc():
    response = client.post(
        '/v1/tenant/membership-revocations',
        json={'subject_id': 'bob'},
        headers={'X-Tenant-ID': str(uuid4())},
    )
    assert response.status_code == 503


def test_session_invalidation_fails_closed_without_oidc():
    response = client.post(
        '/v1/tenant/session-invalidations',
        json={'subject_id': 'bob'},
        headers={'X-Tenant-ID': str(uuid4())},
    )
    assert response.status_code == 503


def test_membership_session_routes_in_openapi_contract():
    spec = app.openapi()
    assert spec['info']['version'] == '0.18.0'
    paths = spec['paths']
    assert 'post' in paths['/v1/tenant/membership-revocations']
    assert 'post' in paths['/v1/tenant/session-invalidations']
    assert 'get' not in paths['/v1/tenant/membership-revocations']
    schema = spec['components']['schemas']['MembershipSessionPosture']
    assert schema['properties']['reason']['enum'] == ['membership_revoked', 'session_kill']
    notice = schema['properties']['notice']
    assert 'Live IdP token revocation is not performed' in notice['const']


def test_enforce_membership_session_rejects_stale_iat():
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = {'not_before': 1_700_000_100}
    with pytest.raises(HTTPException) as exc:
        enforce_membership_session(conn, uuid4(), 'alice', 1_700_000_050)
    assert exc.value.status_code == 401
    assert exc.value.detail == 'Session invalidated; re-authenticate'


def test_enforce_membership_session_allows_fresh_iat():
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = {'not_before': 1_700_000_100}
    enforce_membership_session(conn, uuid4(), 'alice', 1_700_000_100)
    enforce_membership_session(conn, uuid4(), 'alice', 1_700_000_101)


def test_enforce_membership_session_noop_without_rows():
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = {'not_before': 0}
    enforce_membership_session(conn, uuid4(), 'alice', 1)


def test_membership_subject_rejects_blank_and_extra_fields():
    from app.auth import require_mfa
    from app.main import access_token_iat, authorized_db

    def fake_authorized_db():
        yield SimpleNamespace(execute=Mock()), 'owner'

    app.dependency_overrides[authorized_db] = fake_authorized_db
    app.dependency_overrides[access_token_iat] = lambda: 2**31 - 1
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        blank = client.post(
            '/v1/tenant/membership-revocations',
            json={'subject_id': '   '},
            headers={'X-Tenant-ID': str(uuid4())},
        )
        extra = client.post(
            '/v1/tenant/session-invalidations',
            json={'subject_id': 'bob', 'role': 'owner'},
            headers={'X-Tenant-ID': str(uuid4())},
        )
        assert blank.status_code == 422
        assert extra.status_code == 422
        assert blank.json()['detail'] == 'Invalid request'
        assert extra.json()['detail'] == 'Invalid request'
    finally:
        app.dependency_overrides.clear()


def test_owner_only_gate_on_membership_revoke():
    from app.auth import require_mfa
    from app.main import access_token_iat, authorized_db

    def fake_authorized_db():
        yield SimpleNamespace(execute=Mock()), 'editor'

    app.dependency_overrides[authorized_db] = fake_authorized_db
    app.dependency_overrides[access_token_iat] = lambda: 2**31 - 1
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        response = client.post(
            '/v1/tenant/membership-revocations',
            json={'subject_id': 'bob'},
            headers={'X-Tenant-ID': str(uuid4())},
        )
        assert response.status_code == 403
        assert response.json()['detail'] == 'Tenant owner permission required'
    finally:
        app.dependency_overrides.clear()
