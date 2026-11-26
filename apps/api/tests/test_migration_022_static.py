from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / 'infra' / 'db' / '022_evidence_conflict_disposition.sql'


def test_migration_022_defines_append_only_non_title_dispositions():
    text = MIGRATION.read_text(encoding='utf-8')
    assert 'CREATE TABLE public.evidence_conflict_dispositions' in text
    assert 'conflict.disposition_recorded' in text
    assert "outcome text NOT NULL CHECK (outcome IN ('noted', 'kept_unresolved'))" in text
    assert 'verified' not in text.split('outcome text NOT NULL')[1].split('reason text')[0]
    assert 'title' not in text.split('outcome text NOT NULL')[1].split('reason text')[0].lower()
    assert 'does not clear identifier conflict status' in text.lower() or (
        'A disposition does not clear identifier conflict status' in text
    )
    assert 'FORCE ROW LEVEL SECURITY' in text
    assert 'evidence_conflict_dispositions_no_update' in text
    assert 'evidence_conflict_dispositions_no_truncate' in text
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in text
    assert "'none'::text, true" in text
    assert 'REVOKE ALL ON FUNCTION public.record_evidence_conflict_disposition(uuid, uuid, text, uuid, text, text) FROM PUBLIC' in text
    assert 'REVOKE ALL ON FUNCTION public.reject_evidence_conflict_disposition_rewrite() FROM PUBLIC' in text


def test_migration_022_and_provision_runtime_keep_select_only_writes_via_function():
    text = MIGRATION.read_text(encoding='utf-8')
    assert 'GRANT SELECT ON TABLE public.evidence_conflict_dispositions TO oydp_app' in text
    assert 'GRANT EXECUTE ON FUNCTION public.record_evidence_conflict_disposition(uuid, uuid, text, uuid, text, text) TO oydp_app' in text
    assert 'REVOKE ALL ON FUNCTION public.reject_evidence_conflict_disposition_rewrite() FROM oydp_app' in text
    migrate_py = (ROOT / 'scripts' / 'migrate.py').read_text(encoding='utf-8')
    assert 'evidence_conflict_dispositions' in migrate_py
    assert 'GRANT EXECUTE ON FUNCTION public.record_evidence_conflict_disposition(uuid,uuid,text,uuid,text,text) TO oydp_app' in migrate_py
    assert 'REVOKE ALL ON FUNCTION public.reject_evidence_conflict_disposition_rewrite() FROM oydp_app' in migrate_py
