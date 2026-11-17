from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / 'infra' / 'db' / '021_membership_session_posture.sql'


def test_migration_021_defines_session_posture_without_idp():
    text = MIGRATION.read_text(encoding='utf-8')
    assert 'CREATE TABLE public.membership_session_invalidations' in text
    assert 'revoke_tenant_membership' in text
    assert 'invalidate_tenant_member_sessions' in text
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in text
    assert 'FORCE ROW LEVEL SECURITY' in text
    assert 'membership_revoked' in text
    assert 'session_kill' in text
    assert 'without a live IdP' in text
    assert "hashtextextended('oydp-membership/' || t::text, 0)" in text
    assert text.count("hashtextextended('oydp-membership/' || t::text, 0)") == 2
    assert 'floor(extract(epoch FROM clock_timestamp()))::bigint + 1' in text
    assert 'membership_session_invalidations_no_rewrite' in text
    assert 'membership_session_invalidations_no_truncate' in text
    assert 'REVOKE ALL ON FUNCTION public.reject_membership_session_rewrite() FROM PUBLIC' in text


def test_migration_021_revokes_public_execute():
    text = MIGRATION.read_text(encoding='utf-8')
    assert 'REVOKE ALL ON FUNCTION public.revoke_tenant_membership(uuid, text) FROM PUBLIC' in text
    assert 'REVOKE ALL ON FUNCTION public.invalidate_tenant_member_sessions(uuid, text) FROM PUBLIC' in text
    assert 'REVOKE ALL ON FUNCTION public._record_membership_session_invalidation(uuid, text, text, text) FROM PUBLIC' in text
    migrate_py = (ROOT / 'scripts' / 'migrate.py').read_text(encoding='utf-8')
    assert 'GRANT SELECT ON membership_session_invalidations TO oydp_app' in migrate_py
    assert 'REVOKE ALL ON FUNCTION public._record_membership_session_invalidation(uuid, text, text, text) FROM oydp_app' in migrate_py
    assert 'REVOKE ALL ON FUNCTION public.reject_membership_session_rewrite() FROM oydp_app' in migrate_py
