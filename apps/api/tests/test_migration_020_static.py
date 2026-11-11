from pathlib import Path

from scripts.migrate import ROOT


def test_migration_020_keeps_security_definer_search_path_and_revokes_public():
    path = ROOT / '020_runtime_audit_and_source_gates.sql'
    text = path.read_text(encoding='utf-8')
    assert 'SECURITY DEFINER SET search_path = pg_catalog, pg_temp' in text
    for name in (
        'record_property_created_audit',
        'record_document_quarantined_audit',
        'record_diligence_audit',
        'withdraw_evidence_source',
        'attribute_property_document',
    ):
        assert name in text
    assert text.count('REVOKE ALL ON FUNCTION') >= 5
    assert 'DROP POLICY IF EXISTS assertion_creator_insert' in text
    assert "actor_role IS DISTINCT FROM 'owner' AND source_creator IS DISTINCT FROM actor" in text
    assert 'COALESCE(cited_claim, next_claim)' in text


def test_provision_runtime_script_revokes_direct_audit_insert():
    migrate_py = Path(__file__).resolve().parents[3] / 'scripts' / 'migrate.py'
    text = migrate_py.read_text(encoding='utf-8')
    assert "GRANT SELECT ON property_audit_events TO oydp_app" in text
    assert "GRANT SELECT, INSERT ON property_audit_events TO oydp_app" not in text
    assert 'record_property_created_audit' in text
    assert 'GRANT SELECT ON evidence_assertions TO oydp_app' in text
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON properties, evidence_assertions' not in text
