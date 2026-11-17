"""Membership-revoke session posture against real PostgreSQL (no live IdP)."""
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from scripts.migrate import migrate, provision_runtime

DSN = os.getenv('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not DSN, reason='TEST_DATABASE_URL is required for real PostgreSQL tests')
PASSWORD = 'test-runtime-password-24chars'


@pytest.fixture(scope='module', autouse=True)
def _schema():
    migrate(DSN)
    provision_runtime(DSN, PASSWORD)


@pytest.fixture
def api(monkeypatch):
    from fastapi.testclient import TestClient
    from app.auth import require_mfa, verified_subject
    from app.main import app, access_token_iat

    monkeypatch.setenv('DATABASE_URL', make_conninfo(DSN, user='oydp_app', password=PASSWORD))
    app.dependency_overrides[verified_subject] = lambda: 'session-owner'
    app.dependency_overrides[access_token_iat] = lambda: 2**31 - 1
    app.dependency_overrides[require_mfa] = lambda: True
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _seed(tenant, rows):
    with psycopg.connect(DSN) as conn:
        for subject, role in rows:
            conn.execute(
                "INSERT INTO tenant_memberships VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (tenant, subject, role),
            )


def test_session_kill_denies_stale_token_keeps_membership(api):
    from app.auth import verified_subject
    from app.main import app, access_token_iat

    tenant = uuid4()
    _seed(tenant, [('session-owner', 'owner'), ('session-member', 'editor')])
    headers = {'X-Tenant-ID': str(tenant)}
    created = api.post('/v1/properties', headers=headers, json={'label': 'Session property', 'jurisdiction': 'KA'})
    assert created.status_code == 201, created.text
    property_id = created.json()['id']

    killed = api.post('/v1/tenant/session-invalidations', headers=headers, json={'subject_id': 'session-member'})
    assert killed.status_code == 200, killed.text
    body = killed.json()
    assert body['reason'] == 'session_kill'
    assert body['subject_id'] == 'session-member'
    assert 'Live IdP token revocation is not performed' in body['notice']
    not_before = body['not_before_epoch']

    with psycopg.connect(DSN) as conn:
        assert conn.execute(
            "SELECT role FROM tenant_memberships WHERE tenant_id=%s AND subject_id='session-member'",
            (tenant,),
        ).fetchone() == ('editor',)

    app.dependency_overrides[verified_subject] = lambda: 'session-member'
    app.dependency_overrides[access_token_iat] = lambda: not_before - 1
    denied = api.get(f'/v1/properties/{property_id}', headers=headers)
    assert denied.status_code == 401
    assert denied.json()['detail'] == 'Session invalidated; re-authenticate'

    app.dependency_overrides[access_token_iat] = lambda: not_before
    # Member has no read grant on owner-created property without share.
    assert api.get(f'/v1/properties/{property_id}', headers=headers).status_code == 404


def test_membership_revoke_removes_member_and_records_invalidation(api):
    from app.auth import verified_subject
    from app.main import app, access_token_iat

    tenant = uuid4()
    _seed(tenant, [('session-owner', 'owner'), ('session-victim', 'editor')])
    headers = {'X-Tenant-ID': str(tenant)}
    created = api.post('/v1/properties', headers=headers, json={'label': 'Revoked access', 'jurisdiction': 'KA'})
    assert created.status_code == 201, created.text
    property_id = created.json()['id']
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    grant_body = {'recipient_subject': 'session-victim', 'expires_at': expires}
    assert api.put(f'/v1/properties/{property_id}/access', headers=headers, json=grant_body).status_code == 200
    assert api.put(f'/v1/properties/{property_id}/writers', headers=headers, json=grant_body).status_code == 200

    app.dependency_overrides[verified_subject] = lambda: 'session-victim'
    assert api.get(f'/v1/properties/{property_id}', headers=headers).status_code == 200
    app.dependency_overrides[verified_subject] = lambda: 'session-owner'
    app.dependency_overrides[access_token_iat] = lambda: 2**31 - 1

    revoked = api.post(
        '/v1/tenant/membership-revocations',
        headers=headers,
        json={'subject_id': 'session-victim'},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()['reason'] == 'membership_revoked'
    not_before = revoked.json()['not_before_epoch']

    with psycopg.connect(DSN) as conn:
        assert conn.execute(
            "SELECT 1 FROM tenant_memberships WHERE tenant_id=%s AND subject_id='session-victim'",
            (tenant,),
        ).fetchone() is None
        assert conn.execute(
            """SELECT reason FROM membership_session_invalidations
               WHERE tenant_id=%s AND subject_id='session-victim'
               ORDER BY invalidated_at DESC LIMIT 1""",
            (tenant,),
        ).fetchone() == ('membership_revoked',)
        assert conn.execute(
            "SELECT count(*) FROM property_read_grants WHERE tenant_id=%s AND subject_id='session-victim'",
            (tenant,),
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT count(*) FROM property_write_grants WHERE tenant_id=%s AND subject_id='session-victim'",
            (tenant,),
        ).fetchone() == (0,)

    # Membership is gone, so the old token cannot keep using the cascaded grants.
    app.dependency_overrides[verified_subject] = lambda: 'session-victim'
    app.dependency_overrides[access_token_iat] = lambda: not_before
    denied = api.get(f'/v1/properties/{property_id}', headers=headers)
    assert denied.status_code == 403
    assert denied.json()['detail'] == 'Tenant membership required'

    # Re-add membership; stale iat must still fail session posture, and grants stay gone.
    with psycopg.connect(DSN) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships VALUES (%s,'session-victim','viewer')",
            (tenant,),
        )
    app.dependency_overrides[access_token_iat] = lambda: not_before - 1
    assert api.get('/v1/properties', headers=headers).status_code == 401
    app.dependency_overrides[access_token_iat] = lambda: not_before
    assert api.get('/v1/properties', headers=headers).status_code == 200
    assert api.get(f'/v1/properties/{property_id}', headers=headers).status_code == 404


def test_membership_revoke_negatives_authz_and_cross_tenant(api):
    from app.auth import verified_subject
    from app.main import app

    tenant_a, tenant_b = uuid4(), uuid4()
    _seed(tenant_a, [('session-owner', 'owner'), ('session-editor', 'editor'), ('session-viewer', 'viewer')])
    _seed(tenant_b, [('session-b-owner', 'owner'), ('session-foreign', 'viewer')])

    # Unauthenticated / no MFA override cleared briefly.
    app.dependency_overrides.clear()
    bare = api.post(
        '/v1/tenant/membership-revocations',
        headers={'X-Tenant-ID': str(tenant_a)},
        json={'subject_id': 'session-viewer'},
    )
    assert bare.status_code == 503

    from app.auth import require_mfa
    from app.main import access_token_iat
    app.dependency_overrides[require_mfa] = lambda: True
    app.dependency_overrides[access_token_iat] = lambda: 2**31 - 1

    app.dependency_overrides[verified_subject] = lambda: 'session-editor'
    editor = api.post(
        '/v1/tenant/membership-revocations',
        headers={'X-Tenant-ID': str(tenant_a)},
        json={'subject_id': 'session-viewer'},
    )
    assert editor.status_code == 403

    app.dependency_overrides[verified_subject] = lambda: 'session-viewer'
    viewer = api.post(
        '/v1/tenant/session-invalidations',
        headers={'X-Tenant-ID': str(tenant_a)},
        json={'subject_id': 'session-editor'},
    )
    assert viewer.status_code == 403

    app.dependency_overrides[verified_subject] = lambda: 'session-owner'
    cross = api.post(
        '/v1/tenant/membership-revocations',
        headers={'X-Tenant-ID': str(tenant_a)},
        json={'subject_id': 'session-foreign'},
    )
    assert cross.status_code == 404

    self_revoke = api.post(
        '/v1/tenant/membership-revocations',
        headers={'X-Tenant-ID': str(tenant_a)},
        json={'subject_id': 'session-owner'},
    )
    assert self_revoke.status_code == 404

    app.dependency_overrides[verified_subject] = lambda: 'session-b-owner'
    foreign_tenant = api.post(
        '/v1/tenant/membership-revocations',
        headers={'X-Tenant-ID': str(tenant_a)},
        json={'subject_id': 'session-viewer'},
    )
    assert foreign_tenant.status_code == 403


def test_self_revoke_denied_and_sole_owner_preserved(api):
    tenant = uuid4()
    _seed(tenant, [('session-owner', 'owner')])
    headers = {'X-Tenant-ID': str(tenant)}
    self_revoke = api.post(
        '/v1/tenant/membership-revocations',
        headers=headers,
        json={'subject_id': 'session-owner'},
    )
    assert self_revoke.status_code == 404
    with psycopg.connect(make_conninfo(DSN, user='oydp_app', password=PASSWORD)) as conn:
        conn.execute(
            "SELECT set_config('app.tenant_id', %s, true), set_config('app.subject_id', 'session-owner', true)",
            (str(tenant),),
        )
        with pytest.raises(psycopg.Error) as exc:
            conn.execute("SELECT public.revoke_tenant_membership(%s, 'session-owner')", (tenant,))
        assert getattr(exc.value, 'sqlstate', None) == 'P0002'
    with psycopg.connect(DSN) as conn:
        assert conn.execute(
            "SELECT role FROM tenant_memberships WHERE tenant_id=%s AND subject_id='session-owner'",
            (tenant,),
        ).fetchone() == ('owner',)


def test_invalidation_is_tenant_scoped_and_runtime_cannot_forge_it(api):
    from app.auth import verified_subject
    from app.main import app, access_token_iat

    tenant_a, tenant_b = uuid4(), uuid4()
    _seed(tenant_a, [('session-owner', 'owner'), ('session-victim', 'viewer')])
    _seed(tenant_b, [('session-owner', 'owner'), ('session-victim', 'viewer')])
    revoked = api.post(
        '/v1/tenant/membership-revocations',
        headers={'X-Tenant-ID': str(tenant_a)},
        json={'subject_id': 'session-victim'},
    )
    assert revoked.status_code == 200, revoked.text
    stale = revoked.json()['not_before_epoch'] - 1

    with psycopg.connect(DSN) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships VALUES (%s,'session-victim','viewer')",
            (tenant_a,),
        )
    app.dependency_overrides[verified_subject] = lambda: 'session-victim'
    app.dependency_overrides[access_token_iat] = lambda: stale
    assert api.get('/v1/properties', headers={'X-Tenant-ID': str(tenant_a)}).status_code == 401
    assert api.get('/v1/properties', headers={'X-Tenant-ID': str(tenant_b)}).status_code == 200

    app_dsn = make_conninfo(DSN, user='oydp_app', password=PASSWORD)
    with psycopg.connect(app_dsn) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_b),))
        conn.execute("SELECT set_config('app.subject_id', 'session-owner', false)")
        with pytest.raises(psycopg.Error) as insert_exc:
            conn.execute(
                """INSERT INTO membership_session_invalidations
                   (tenant_id, subject_id, not_before_epoch, reason, actor_subject)
                   VALUES (%s, 'session-victim', 1, 'session_kill', 'session-owner')""",
                (tenant_b,),
            )
        assert insert_exc.value.sqlstate == '42501'
        conn.rollback()
        with pytest.raises(psycopg.Error) as call_exc:
            conn.execute(
                "SELECT public._record_membership_session_invalidation(%s, 'session-victim', 'session-owner', 'session_kill')",
                (tenant_b,),
            )
        assert call_exc.value.sqlstate == '42501'
        conn.rollback()
        with pytest.raises(psycopg.Error) as delete_exc:
            conn.execute(
                "DELETE FROM membership_session_invalidations WHERE tenant_id=%s",
                (tenant_a,),
            )
        assert delete_exc.value.sqlstate == '42501'
        conn.rollback()
    with psycopg.connect(DSN) as conn:
        with pytest.raises(psycopg.Error) as rewrite_exc:
            conn.execute(
                "UPDATE membership_session_invalidations SET reason='session_kill' WHERE tenant_id=%s",
                (tenant_a,),
            )
        assert rewrite_exc.value.sqlstate == '42501'
        conn.rollback()
        with pytest.raises(psycopg.Error) as truncate_exc:
            conn.execute('TRUNCATE membership_session_invalidations')
        assert truncate_exc.value.sqlstate == '42501'
        conn.rollback()


def test_concurrent_owner_revokes_leave_one_owner(api):
    """Two owners revoking each other must overlap on the tenant lock and leave one owner."""
    tenant = uuid4()
    _seed(tenant, [('owner-a', 'owner'), ('owner-b', 'owner')])
    app_dsn = make_conninfo(DSN, user='oydp_app', password=PASSWORD)
    started = threading.Barrier(2)
    held = threading.Event()
    results = {}

    def winner():
        with psycopg.connect(app_dsn) as conn:
            conn.execute("SET statement_timeout = '15000'")
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
            conn.execute("SELECT set_config('app.subject_id', 'owner-a', true)")
            started.wait(timeout=15)
            conn.execute("SELECT public.revoke_tenant_membership(%s, 'owner-b')", (tenant,))
            held.set()
            deadline = time.monotonic() + 5
            overlapped = False
            while time.monotonic() < deadline:
                with psycopg.connect(DSN) as watch:
                    waiting = watch.execute(
                        """SELECT 1 FROM pg_stat_activity
                           WHERE application_name = 'membership-loser'
                             AND wait_event_type = 'Lock'"""
                    ).fetchone()
                if waiting:
                    overlapped = True
                    break
                time.sleep(0.05)
            results['overlapped'] = overlapped
            conn.commit()
            results['winner'] = 'ok'

    def loser():
        try:
            with psycopg.connect(app_dsn) as conn:
                conn.execute("SET application_name = 'membership-loser'")
                conn.execute("SET statement_timeout = '15000'")
                conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
                conn.execute("SELECT set_config('app.subject_id', 'owner-b', true)")
                started.wait(timeout=15)
                assert held.wait(timeout=10)
                try:
                    conn.execute("SELECT public.revoke_tenant_membership(%s, 'owner-a')", (tenant,))
                    conn.commit()
                    results['loser'] = 'ok'
                except psycopg.Error as exc:
                    conn.rollback()
                    results['loser'] = exc.sqlstate
        except Exception as exc:
            results['loser'] = getattr(exc, 'sqlstate', None) or type(exc).__name__

    workers = (threading.Thread(target=winner), threading.Thread(target=loser))
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(25)
    assert not any(worker.is_alive() for worker in workers)
    assert results.get('overlapped') is True
    assert results.get('winner') == 'ok'
    # The waiting owner was deleted by the winner, so the lock releases into a denial.
    assert results.get('loser') in ('P0001', 'P0002')
    with psycopg.connect(DSN) as conn:
        owners = conn.execute(
            "SELECT subject_id FROM tenant_memberships WHERE tenant_id=%s AND role='owner' ORDER BY subject_id",
            (tenant,),
        ).fetchall()
    assert [row[0] for row in owners] == ['owner-a']
