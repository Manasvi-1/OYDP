"""Cross-tenant IDOR matrix against disposable PostgreSQL using the oydp_app role.

Attacker holds a valid membership in tenant B and targets tenant A resource IDs
while sending X-Tenant-ID for B (or forging A without membership). Expected denials
are non-disclosing 404 for property-scoped probes with foreign membership, and 403
when membership is missing. Never run against production data.

File name uses the test_z_ prefix so pytest collects it after test_database.py.
Migrating first would make test_database's assert migrate(DSN) fail on an empty list.
"""
import os
from base64 import urlsafe_b64encode
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
    app.dependency_overrides[verified_subject] = lambda: 'idor-alice'
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def tenants(api):
    """Two isolated tenants with Owner/Editor/Reader each, plus one property in A."""
    from app.auth import verified_subject
    from app.main import app

    tenant_a, tenant_b = uuid4(), uuid4()
    subjects = {
        'a_owner': 'idor-a-owner',
        'a_editor': 'idor-a-editor',
        'a_reader': 'idor-a-reader',
        'b_owner': 'idor-b-owner',
        'b_editor': 'idor-b-editor',
        'b_reader': 'idor-b-reader',
    }
    with psycopg.connect(DSN) as conn:
        conn.execute(
            """INSERT INTO tenant_memberships VALUES
              (%s,%s,'owner'),(%s,%s,'editor'),(%s,%s,'viewer'),
              (%s,%s,'owner'),(%s,%s,'editor'),(%s,%s,'viewer')""",
            (
                tenant_a, subjects['a_owner'], tenant_a, subjects['a_editor'], tenant_a, subjects['a_reader'],
                tenant_b, subjects['b_owner'], tenant_b, subjects['b_editor'], tenant_b, subjects['b_reader'],
            ),
        )
    app.dependency_overrides[verified_subject] = lambda: subjects['a_owner']
    headers_a = {'X-Tenant-ID': str(tenant_a)}
    created = api.post(
        '/v1/properties',
        headers=headers_a,
        json={'label': 'Tenant A vault', 'jurisdiction': 'Bengaluru Urban'},
    )
    assert created.status_code == 201, created.text
    property_a = created.json()['id']
    secret_claim = 'CROSS-TENANT-SECRET-CLAIM-TEXT'
    claim = api.post(
        f'/v1/properties/{property_a}/claims',
        headers=headers_a,
        json={'statement': secret_claim},
    )
    assert claim.status_code == 201, claim.text

    def as_subject(subject: str):
        app.dependency_overrides[verified_subject] = lambda: subject

    return {
        'tenant_a': tenant_a,
        'tenant_b': tenant_b,
        'property_a': property_a,
        'secret_claim': secret_claim,
        'subjects': subjects,
        'headers_a': headers_a,
        'headers_b': {'X-Tenant-ID': str(tenant_b)},
        'as_subject': as_subject,
    }


def _assert_hidden(response, secret: str | None = None):
    assert response.status_code in (403, 404), response.text
    if secret:
        assert secret not in response.text


def _pdf():
    return b'%PDF-1.4\n%OYDP-SYNTHETIC-CLEAN\n%%EOF'


def _upload(api, headers, property_id, body, media='application/pdf'):
    sent = dict(headers)
    sent['Content-Type'] = media
    return api.post(f'/v1/properties/{property_id}/documents', headers=sent, content=body)


class _GateScanner:
    def scan(self, payload, media_type):
        if b'OYDP-SYNTHETIC-CLEAN' not in payload:
            return 'fail'
        return 'pass'


def test_uuid_swap_get_patch_delete_and_list_enumeration(api, tenants):
    """UUID swap reads/writes + list must not leak tenant A (scenarios 1–4, 16)."""
    t = tenants
    pid = t['property_a']
    secret = t['secret_claim']
    t['as_subject'](t['subjects']['b_owner'])
    hb = t['headers_b']

    listed = api.get('/v1/properties', headers=hb)
    assert listed.status_code == 200
    assert all(item['id'] != pid for item in listed.json()['items'])
    assert secret not in listed.text

    _assert_hidden(api.get(f'/v1/properties/{pid}', headers=hb), secret)
    _assert_hidden(api.get(f'/v1/properties/{pid}/claims', headers=hb), secret)
    _assert_hidden(api.get(f'/v1/properties/{pid}/corrections', headers=hb), secret)
    _assert_hidden(
        api.patch(f'/v1/properties/{pid}', headers=hb, json={'label': 'stolen', 'jurisdiction': 'KA'}),
        secret,
    )
    _assert_hidden(
        api.request(
            'DELETE',
            f'/v1/properties/{pid}/access',
            headers=hb,
            json={'recipient_subject': t['subjects']['a_reader']},
        ),
        secret,
    )

    # Forged X-Tenant-ID for A without membership.
    forged = api.get(f'/v1/properties/{pid}', headers=t['headers_a'])
    assert forged.status_code == 403
    assert secret not in forged.text


def test_grants_reviews_consent_export_cross_tenant(api, tenants):
    """Share/writer/review/consent/export probes from tenant B must stay opaque."""
    t = tenants
    pid = t['property_a']
    secret = t['secret_claim']
    expiry = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    t['as_subject'](t['subjects']['b_owner'])
    hb = t['headers_b']

    _assert_hidden(
        api.put(
            f'/v1/properties/{pid}/access',
            headers=hb,
            json={'recipient_subject': t['subjects']['b_reader'], 'expires_at': expiry},
        ),
        secret,
    )
    _assert_hidden(api.get(f'/v1/properties/{pid}/writers', headers=hb), secret)
    _assert_hidden(
        api.put(
            f'/v1/properties/{pid}/writers',
            headers=hb,
            json={'recipient_subject': t['subjects']['b_editor'], 'expires_at': expiry},
        ),
        secret,
    )
    _assert_hidden(
        api.request(
            'DELETE',
            f'/v1/properties/{pid}/writers',
            headers=hb,
            json={'recipient_subject': t['subjects']['a_editor']},
        ),
        secret,
    )
    _assert_hidden(api.get(f'/v1/properties/{pid}/reviews', headers=hb), secret)
    _assert_hidden(
        api.post(
            f'/v1/properties/{pid}/reviews',
            headers=hb,
            json={'disposition': 'recorded', 'statement': 'Cross-tenant review must fail'},
        ),
        secret,
    )
    _assert_hidden(
        api.post(f'/v1/properties/{pid}/consents', headers=hb, json={'purpose': 'passport_export'}),
        secret,
    )
    _assert_hidden(
        api.request(
            'DELETE',
            f'/v1/properties/{pid}/consents',
            headers=hb,
            json={'purpose': 'passport_export'},
        ),
        secret,
    )
    _assert_hidden(api.post(f'/v1/properties/{pid}/exports', headers=hb), secret)


def test_documents_scan_identifiers_audit_diligence_cross_tenant(api, tenants, monkeypatch):
    """Document/scan/identifier/audit/diligence IDOR with valid foreign membership."""
    from app.documents import get_document_scanner
    from app.main import app

    t = tenants
    pid = t['property_a']
    secret = t['secret_claim']
    t['as_subject'](t['subjects']['a_owner'])
    ha = t['headers_a']

    monkeypatch.setenv('DOCUMENT_STORAGE_KEY', urlsafe_b64encode(b'I' * 32).decode())
    app.dependency_overrides[get_document_scanner] = lambda: _GateScanner()

    uploaded = _upload(api, ha, pid, _pdf())
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()['id']
    assert 'ciphertext' not in uploaded.json()

    recorded = api.post(
        f'/v1/properties/{pid}/identifiers',
        headers=ha,
        json={'scheme': 'survey', 'identifier_value': 'IDOR-A-1'},
    )
    assert recorded.status_code == 200, recorded.text
    opened = api.post(
        f'/v1/properties/{pid}/requests',
        headers=ha,
        json={'title': 'Private diligence', 'body': 'Do not leak across tenants'},
    )
    assert opened.status_code == 201, opened.text
    request_id = opened.json()['id']

    t['as_subject'](t['subjects']['b_owner'])
    hb = t['headers_b']
    _assert_hidden(api.get(f'/v1/properties/{pid}/documents', headers=hb), secret)
    _assert_hidden(api.get(f'/v1/properties/{pid}/documents/{document_id}', headers=hb), secret)
    _assert_hidden(
        api.get(f'/v1/properties/{pid}/documents/{document_id}/content', headers=hb),
        'OYDP-SYNTHETIC-CLEAN',
    )
    _assert_hidden(
        api.post(f'/v1/properties/{pid}/documents/{document_id}/scan', headers=hb),
        'OYDP-SYNTHETIC-CLEAN',
    )
    _assert_hidden(api.get(f'/v1/properties/{pid}/identifiers', headers=hb), 'IDOR-A-1')
    _assert_hidden(api.get(f'/v1/properties/{pid}/audit', headers=hb), secret)
    _assert_hidden(api.get(f'/v1/properties/{pid}/requests', headers=hb), 'Private diligence')
    _assert_hidden(
        api.get(f'/v1/properties/{pid}/requests/{request_id}/notes', headers=hb),
        'Private diligence',
    )
    _assert_hidden(
        api.post(
            f'/v1/properties/{pid}/requests/{request_id}/notes',
            headers=hb,
            json={'body': 'intrusion'},
        ),
        'Private diligence',
    )
    _assert_hidden(api.post(f'/v1/properties/{pid}/requests/{request_id}/close', headers=hb), 'Private diligence')
    _assert_hidden(
        api.post(f'/v1/properties/{pid}/requests', headers=hb, json={'title': 'x', 'body': 'y'}),
        secret,
    )


def test_missing_revoked_membership_and_expired_grants(api, tenants):
    """Missing/revoked membership, grant revoke, and reshare denial."""
    t = tenants
    pid = t['property_a']
    secret = t['secret_claim']
    ha = t['headers_a']
    peer = 'idor-grant-peer-' + str(uuid4())
    with psycopg.connect(DSN) as conn:
        conn.execute("INSERT INTO tenant_memberships VALUES (%s,%s,'viewer')", (t['tenant_a'], peer))

    t['as_subject'](t['subjects']['a_owner'])
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    expired = api.put(
        f'/v1/properties/{pid}/access',
        headers=ha,
        json={'recipient_subject': peer, 'expires_at': past},
    )
    assert expired.status_code in (404, 422)
    granted = api.put(
        f'/v1/properties/{pid}/access',
        headers=ha,
        json={'recipient_subject': peer, 'expires_at': future},
    )
    assert granted.status_code == 200, granted.text

    t['as_subject'](peer)
    assert api.get(f'/v1/properties/{pid}', headers=ha).status_code == 200
    reshare = api.put(
        f'/v1/properties/{pid}/access',
        headers=ha,
        json={'recipient_subject': t['subjects']['a_reader'], 'expires_at': future},
    )
    assert reshare.status_code == 404
    assert secret not in reshare.text

    t['as_subject'](t['subjects']['a_owner'])
    assert api.request(
        'DELETE',
        f'/v1/properties/{pid}/access',
        headers=ha,
        json={'recipient_subject': peer},
    ).json()['changed'] is True
    t['as_subject'](peer)
    revoked = api.get(f'/v1/properties/{pid}', headers=ha)
    assert revoked.status_code == 404
    assert secret not in revoked.text

    with psycopg.connect(DSN) as conn:
        conn.execute(
            "DELETE FROM tenant_memberships WHERE tenant_id=%s AND subject_id=%s",
            (t['tenant_a'], peer),
        )
    missing = api.get(f'/v1/properties/{pid}', headers=ha)
    assert missing.status_code == 403


def test_role_privilege_escalation_and_pagination_cursor_isolation(api, tenants):
    """Reader cannot perform owner writes; cursor from A cannot be reused under B."""
    t = tenants
    pid = t['property_a']
    secret = t['secret_claim']
    t['as_subject'](t['subjects']['a_reader'])
    ha = t['headers_a']
    # Tenant-wide role denial is 403; property-scoped denials stay non-disclosing 404.
    assert api.post('/v1/properties', headers=ha, json={'label': 'escalation', 'jurisdiction': 'KA'}).status_code == 403
    claim_denied = api.post(f'/v1/properties/{pid}/claims', headers=ha, json={'statement': 'escalate'})
    assert claim_denied.status_code == 404
    assert secret not in claim_denied.text
    consent_denied = api.post(
        f'/v1/properties/{pid}/consents',
        headers=ha,
        json={'purpose': 'passport_export'},
    )
    assert consent_denied.status_code == 404
    assert secret not in consent_denied.text

    t['as_subject'](t['subjects']['a_owner'])
    # Create a second property so a next_cursor is issued.
    assert api.post(
        '/v1/properties',
        headers=ha,
        json={'label': 'Tenant A second', 'jurisdiction': 'KA'},
    ).status_code == 201
    page = api.get('/v1/properties?limit=1', headers=ha)
    assert page.status_code == 200
    cursor = page.json().get('next_cursor')
    assert cursor
    t['as_subject'](t['subjects']['b_owner'])
    reused = api.get(f'/v1/properties?limit=1&cursor={cursor}', headers=t['headers_b'])
    assert reused.status_code == 422
    assert secret not in reused.text


def test_runtime_role_cannot_bypass_rls_for_foreign_property():
    """Direct SQL as oydp_app with tenant B context must not see tenant A rows."""
    tenant_a, tenant_b, property_a = uuid4(), uuid4(), uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships VALUES (%s,'idor-sql-a','owner'),(%s,'idor-sql-b','owner')",
            (tenant_a, tenant_b),
        )
        conn.execute(
            "INSERT INTO properties(id,tenant_id,label,jurisdiction,created_by) VALUES (%s,%s,'SQL A','KA','idor-sql-a')",
            (property_a, tenant_a),
        )
    with psycopg.connect(make_conninfo(DSN, user='oydp_app', password=PASSWORD)) as conn:
        assert conn.execute('SELECT current_user').fetchone()[0] == 'oydp_app'
        assert conn.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone() == (False, False)
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_b),))
        conn.execute("SELECT set_config('app.subject_id', %s, true)", ('idor-sql-b',))
        assert conn.execute('SELECT id FROM properties WHERE id=%s', (property_a,)).fetchall() == []
        assert conn.execute('UPDATE properties SET label=%s WHERE id=%s', ('stolen', property_a)).rowcount == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO properties(tenant_id,label,jurisdiction) VALUES (%s,'x','KA')",
                (tenant_a,),
            )


def test_security_definer_rejects_tenant_mismatch():
    """SECURITY DEFINER helpers compare caller tenant GUC to the passed tenant argument."""
    tenant_a, tenant_b, property_a = uuid4(), uuid4(), uuid4()
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships VALUES (%s,'idor-sd-a','owner'),(%s,'idor-sd-b','owner')",
            (tenant_a, tenant_b),
        )
        conn.execute(
            "INSERT INTO properties(id,tenant_id,label,jurisdiction,created_by) VALUES (%s,%s,'SD A','KA','idor-sd-a')",
            (property_a, tenant_a),
        )
    with psycopg.connect(make_conninfo(DSN, user='oydp_app', password=PASSWORD)) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_b),))
        conn.execute("SELECT set_config('app.subject_id', %s, true)", ('idor-sd-b',))
        with pytest.raises(psycopg.Error):
            conn.execute(
                "SELECT public.set_property_read_access(%s, %s, %s, %s)",
                (tenant_a, property_a, 'idor-sd-b', datetime.now(timezone.utc) + timedelta(days=1)),
            )


def test_mfa_still_required_on_high_risk_cross_tenant_path(api, tenants):
    from app.auth import require_mfa
    from app.main import app

    t = tenants
    app.dependency_overrides[require_mfa] = lambda: (_ for _ in ()).throw(
        HTTPException(403, 'MFA access token required')
    )
    t['as_subject'](t['subjects']['b_owner'])
    denied = api.post(f'/v1/properties/{t["property_a"]}/exports', headers=t['headers_b'])
    assert denied.status_code == 403
    assert t['secret_claim'] not in denied.text
