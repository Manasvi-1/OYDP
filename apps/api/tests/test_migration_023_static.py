from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / 'infra' / 'db' / '023_property_dedup_candidates.sql'


def test_migration_023_defines_candidate_only_non_merge_dedup():
    text = MIGRATION.read_text(encoding='utf-8')
    assert 'CREATE TABLE public.property_dedup_candidates' in text
    assert 'CREATE TABLE public.property_dedup_reviews' in text
    assert 'dedup.candidate_recorded' in text
    assert 'dedup.review_recorded' in text
    assert "outcome text NOT NULL CHECK (outcome IN (\n  'keep_separate', 'flag_possible_duplicate', 'needs_more_evidence'))" in text
    outcome_block = text.split('outcome text NOT NULL')[1].split('reason text')[0].lower()
    assert 'merge' not in outcome_block
    assert 'verified' not in outcome_block
    assert 'title' not in outcome_block
    assert 'Does not merge properties' in text
    assert 'FORCE ROW LEVEL SECURITY' in text
    assert 'property_dedup_candidates_no_delete' in text
    assert 'property_dedup_reviews_no_update' in text
    assert 'property_dedup_reviews_no_truncate' in text
    assert "SECURITY DEFINER SET search_path = pg_catalog, pg_temp" in text
    assert 'properties_merged boolean' in text
    assert "'none'::text" in text
    assert 'merge_properties' in text  # explicit refusal check
    assert 'Property merge helpers must not exist' in text
    assert 'REVOKE ALL ON FUNCTION public.generate_property_dedup_candidates(uuid) FROM PUBLIC' in text
    assert 'REVOKE ALL ON FUNCTION public.record_property_dedup_review(uuid, uuid, text, text) FROM PUBLIC' in text


def test_migration_023_and_provision_runtime_keep_select_only_writes_via_function():
    text = MIGRATION.read_text(encoding='utf-8')
    assert 'GRANT SELECT ON TABLE public.property_dedup_candidates TO oydp_app' in text
    assert 'GRANT SELECT ON TABLE public.property_dedup_reviews TO oydp_app' in text
    assert 'GRANT EXECUTE ON FUNCTION public.generate_property_dedup_candidates(uuid) TO oydp_app' in text
    assert 'GRANT EXECUTE ON FUNCTION public.record_property_dedup_review(uuid, uuid, text, text) TO oydp_app' in text
    assert 'REVOKE ALL ON FUNCTION public.reject_property_dedup_rewrite() FROM oydp_app' in text
    migrate_py = (ROOT / 'scripts' / 'migrate.py').read_text(encoding='utf-8')
    assert 'property_dedup_candidates' in migrate_py
    assert 'property_dedup_reviews' in migrate_py
    assert 'GRANT EXECUTE ON FUNCTION public.generate_property_dedup_candidates(uuid) TO oydp_app' in migrate_py
    assert 'GRANT EXECUTE ON FUNCTION public.record_property_dedup_review(uuid,uuid,text,text) TO oydp_app' in migrate_py
    assert 'REVOKE ALL ON FUNCTION public.reject_property_dedup_rewrite() FROM oydp_app' in migrate_py
    assert 'REVOKE ALL ON FUNCTION public.reject_property_dedup_review_rewrite() FROM oydp_app' in migrate_py
    assert 'REVOKE ALL ON FUNCTION public.reject_property_dedup_candidate_unsafe_update() FROM oydp_app' in migrate_py
