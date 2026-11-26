-- Property deduplication CANDIDATES only.
-- Same-tenant, evidence-based similarity. Not title proof.
-- Does not merge properties, verify claims, clear identifier conflicts,
-- or assert ownership. Follows 022_evidence_conflict_disposition.sql.

ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK (event_type IN (
  'property.created','access.granted','access.revoked','claim.recorded','property.corrected',
  'write.granted','write.revoked','document.quarantined','document.scan_passed','document.scan_failed',
  'document.attributed',
  'identifier.recorded','identifier.conflict','review.recorded','consent.recorded','consent.revoked','packet.exported',
  'diligence.opened','diligence.noted','diligence.closed',
  'conflict.disposition_recorded',
  'dedup.candidate_recorded','dedup.review_recorded'));
ALTER TABLE public.property_audit_events DROP CONSTRAINT access_audit_shape;
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type = 'property.created' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'claim.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NOT NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'property.corrected' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NOT NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'write.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'write.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type IN ('document.quarantined','document.scan_passed','document.scan_failed','document.attributed') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NOT NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type IN ('identifier.recorded','identifier.conflict') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NOT NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'review.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NOT NULL AND consent_id IS NULL)
 OR (event_type IN ('consent.recorded','consent.revoked','packet.exported') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NOT NULL)
 OR (event_type IN (
      'diligence.opened','diligence.noted','diligence.closed','conflict.disposition_recorded',
      'dedup.candidate_recorded','dedup.review_recorded')
     AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL
     AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL));

CREATE TABLE public.property_dedup_candidates (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_a_id uuid NOT NULL,
 property_b_id uuid NOT NULL,
 match_basis text NOT NULL CHECK (match_basis IN ('shared_identifier', 'normalized_label')),
 match_scheme text NOT NULL DEFAULT '' CHECK (
  (match_basis = 'shared_identifier' AND match_scheme IN ('internal','survey','municipal','khata'))
  OR (match_basis = 'normalized_label' AND match_scheme = '')),
 match_value_normalized text NOT NULL CHECK (
  length(match_value_normalized) BETWEEN 1 AND 200
  AND match_value_normalized = lower(btrim(match_value_normalized))
  AND match_value_normalized !~ '[[:cntrl:]]'),
 status text NOT NULL DEFAULT 'open' CHECK (status IN (
  'open',
  'reviewed_keep_separate',
  'reviewed_possible_duplicate',
  'reviewed_needs_more_evidence')),
 generated_by text NOT NULL CHECK (length(generated_by) BETWEEN 1 AND 255),
 generated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK (property_a_id < property_b_id),
 UNIQUE (tenant_id, property_a_id, property_b_id, match_basis, match_scheme, match_value_normalized),
 UNIQUE (tenant_id, id),
 FOREIGN KEY (tenant_id, property_a_id) REFERENCES public.properties (tenant_id, id),
 FOREIGN KEY (tenant_id, property_b_id) REFERENCES public.properties (tenant_id, id)
);
CREATE INDEX property_dedup_candidates_page_idx
 ON public.property_dedup_candidates (tenant_id, generated_at DESC, id DESC);
ALTER TABLE public.property_dedup_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_dedup_candidates FORCE ROW LEVEL SECURITY;
-- Visible only when both properties are readable under private property RLS.
CREATE POLICY property_dedup_candidate_read ON public.property_dedup_candidates FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (
  SELECT 1 FROM public.properties p
  WHERE p.tenant_id = property_dedup_candidates.tenant_id
    AND p.id = property_dedup_candidates.property_a_id)
 AND EXISTS (
  SELECT 1 FROM public.properties p
  WHERE p.tenant_id = property_dedup_candidates.tenant_id
    AND p.id = property_dedup_candidates.property_b_id)
);
REVOKE ALL ON public.property_dedup_candidates FROM PUBLIC;

CREATE TABLE public.property_dedup_reviews (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 candidate_id uuid NOT NULL,
 outcome text NOT NULL CHECK (outcome IN (
  'keep_separate', 'flag_possible_duplicate', 'needs_more_evidence')),
 reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 500),
 recorded_by text NOT NULL CHECK (length(recorded_by) BETWEEN 1 AND 255),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE (tenant_id, id),
 FOREIGN KEY (tenant_id, candidate_id) REFERENCES public.property_dedup_candidates (tenant_id, id)
);
CREATE INDEX property_dedup_reviews_page_idx
 ON public.property_dedup_reviews (tenant_id, candidate_id, recorded_at DESC, id DESC);
ALTER TABLE public.property_dedup_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_dedup_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY property_dedup_review_read ON public.property_dedup_reviews FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (
  SELECT 1 FROM public.property_dedup_candidates c
  WHERE c.tenant_id = property_dedup_reviews.tenant_id
    AND c.id = property_dedup_reviews.candidate_id)
);
REVOKE ALL ON public.property_dedup_reviews FROM PUBLIC;

CREATE FUNCTION public.reject_property_dedup_rewrite()
 RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 RAISE EXCEPTION 'Property dedup records are append-only except status via review' USING ERRCODE = '42501';
END $$;
REVOKE ALL ON FUNCTION public.reject_property_dedup_rewrite() FROM PUBLIC;

CREATE FUNCTION public.reject_property_dedup_review_rewrite()
 RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 RAISE EXCEPTION 'Property dedup reviews are append-only' USING ERRCODE = '42501';
END $$;
REVOKE ALL ON FUNCTION public.reject_property_dedup_review_rewrite() FROM PUBLIC;

-- Candidates: no DELETE/TRUNCATE; UPDATE only of status column is allowed from SECURITY DEFINER.
CREATE FUNCTION public.reject_property_dedup_candidate_unsafe_update()
 RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN
  RAISE EXCEPTION 'Property dedup records are append-only except status via review' USING ERRCODE = '42501';
 END IF;
 IF NEW.id IS DISTINCT FROM OLD.id
  OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
  OR NEW.property_a_id IS DISTINCT FROM OLD.property_a_id
  OR NEW.property_b_id IS DISTINCT FROM OLD.property_b_id
  OR NEW.match_basis IS DISTINCT FROM OLD.match_basis
  OR NEW.match_scheme IS DISTINCT FROM OLD.match_scheme
  OR NEW.match_value_normalized IS DISTINCT FROM OLD.match_value_normalized
  OR NEW.generated_by IS DISTINCT FROM OLD.generated_by
  OR NEW.generated_at IS DISTINCT FROM OLD.generated_at THEN
  RAISE EXCEPTION 'Property dedup records are append-only except status via review' USING ERRCODE = '42501';
 END IF;
 IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
  RAISE EXCEPTION 'Property dedup records are append-only except status via review' USING ERRCODE = '42501';
 END IF;
 IF NEW.status NOT IN (
  'reviewed_keep_separate', 'reviewed_possible_duplicate', 'reviewed_needs_more_evidence') THEN
  RAISE EXCEPTION 'Property dedup records are append-only except status via review' USING ERRCODE = '42501';
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.reject_property_dedup_candidate_unsafe_update() FROM PUBLIC;

CREATE TRIGGER property_dedup_candidates_guard_update
 BEFORE UPDATE ON public.property_dedup_candidates
 FOR EACH ROW EXECUTE FUNCTION public.reject_property_dedup_candidate_unsafe_update();
CREATE TRIGGER property_dedup_candidates_no_delete
 BEFORE DELETE ON public.property_dedup_candidates
 FOR EACH ROW EXECUTE FUNCTION public.reject_property_dedup_rewrite();
CREATE TRIGGER property_dedup_candidates_no_truncate
 BEFORE TRUNCATE ON public.property_dedup_candidates
 FOR EACH STATEMENT EXECUTE FUNCTION public.reject_property_dedup_rewrite();
CREATE TRIGGER property_dedup_reviews_no_update
 BEFORE UPDATE OR DELETE ON public.property_dedup_reviews
 FOR EACH ROW EXECUTE FUNCTION public.reject_property_dedup_review_rewrite();
CREATE TRIGGER property_dedup_reviews_no_truncate
 BEFORE TRUNCATE ON public.property_dedup_reviews
 FOR EACH STATEMENT EXECUTE FUNCTION public.reject_property_dedup_review_rewrite();

CREATE FUNCTION public.generate_property_dedup_candidates(t uuid)
 RETURNS TABLE (
  created_count integer,
  skipped_existing integer,
  considered_pairs integer,
  properties_merged boolean,
  title_effect text)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
 actor text := nullif(current_setting('app.subject_id', true), '');
 created integer := 0;
 skipped integer := 0;
 considered integer := 0;
 pair record;
 new_id uuid;
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM 1 FROM public.tenant_memberships
  WHERE tenant_id = t AND subject_id = actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/dedup-generate', 0));

 FOR pair IN
  WITH editable AS (
   SELECT p.id, lower(btrim(p.label)) AS norm_label
   FROM public.properties p
   WHERE p.tenant_id = t AND public.actor_can_edit_property(t, p.id)
  ),
  id_pairs AS (
   SELECT DISTINCT
    LEAST(a.property_id, b.property_id) AS property_a_id,
    GREATEST(a.property_id, b.property_id) AS property_b_id,
    'shared_identifier'::text AS match_basis,
    a.scheme AS match_scheme,
    lower(btrim(a.identifier_value)) AS match_value_normalized
   FROM public.property_identifiers a
   JOIN public.property_identifiers b
     ON a.tenant_id = b.tenant_id
    AND a.scheme = b.scheme
    AND lower(btrim(a.identifier_value)) = lower(btrim(b.identifier_value))
    AND a.property_id < b.property_id
    AND a.status IN ('current', 'conflict')
    AND b.status IN ('current', 'conflict')
   WHERE a.tenant_id = t
     AND EXISTS (SELECT 1 FROM editable e WHERE e.id = a.property_id)
     AND EXISTS (SELECT 1 FROM editable e WHERE e.id = b.property_id)
     AND length(lower(btrim(a.identifier_value))) BETWEEN 1 AND 200
  ),
  label_pairs AS (
   SELECT
    LEAST(a.id, b.id) AS property_a_id,
    GREATEST(a.id, b.id) AS property_b_id,
    'normalized_label'::text AS match_basis,
    ''::text AS match_scheme,
    a.norm_label AS match_value_normalized
   FROM editable a
   JOIN editable b ON a.norm_label = b.norm_label AND a.id < b.id
   WHERE length(a.norm_label) BETWEEN 1 AND 200
  ),
  candidates AS (
   SELECT * FROM id_pairs
   UNION ALL
   SELECT * FROM label_pairs
  )
  SELECT c.property_a_id, c.property_b_id, c.match_basis, c.match_scheme, c.match_value_normalized
  FROM candidates c
  -- Prefer identifier evidence over label matches; both remain candidates only.
  ORDER BY CASE c.match_basis WHEN 'shared_identifier' THEN 0 ELSE 1 END,
           c.match_scheme, c.match_value_normalized, c.property_a_id, c.property_b_id
  LIMIT 500
 LOOP
  considered := considered + 1;
  IF created >= 100 THEN
   skipped := skipped + 1;
   CONTINUE;
  END IF;
  INSERT INTO public.property_dedup_candidates (
   tenant_id, property_a_id, property_b_id, match_basis, match_scheme,
   match_value_normalized, generated_by)
  VALUES (
   t, pair.property_a_id, pair.property_b_id, pair.match_basis, pair.match_scheme,
   pair.match_value_normalized, actor)
  ON CONFLICT (tenant_id, property_a_id, property_b_id, match_basis, match_scheme, match_value_normalized)
  DO NOTHING
  RETURNING public.property_dedup_candidates.id INTO new_id;
  IF new_id IS NULL THEN
   skipped := skipped + 1;
  ELSE
   created := created + 1;
   INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type)
   VALUES (t, pair.property_a_id, actor, 'dedup.candidate_recorded');
   new_id := NULL;
  END IF;
 END LOOP;

 RETURN QUERY SELECT created, skipped, considered, false, 'none'::text;
END $$;
REVOKE ALL ON FUNCTION public.generate_property_dedup_candidates(uuid) FROM PUBLIC;

CREATE FUNCTION public.record_property_dedup_review(
  t uuid, candidate uuid, note_outcome text, note_reason text)
 RETURNS TABLE (
  id uuid, tenant_id uuid, candidate_id uuid, outcome text, reason text,
  recorded_by text, recorded_at timestamptz,
  candidate_status text, properties_merged boolean, title_effect text,
  verification_unchanged boolean)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
 actor text := nullif(current_setting('app.subject_id', true), '');
 new_id uuid;
 prop_a uuid;
 prop_b uuid;
 next_status text;
BEGIN
 note_reason := btrim(note_reason);
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL
  OR candidate IS NULL
  OR note_outcome IS NULL OR note_outcome NOT IN (
    'keep_separate', 'flag_possible_duplicate', 'needs_more_evidence')
  OR note_reason IS NULL OR length(note_reason) NOT BETWEEN 1 AND 500
  OR note_reason ~ '[[:cntrl:]]' THEN
  RAISE EXCEPTION 'Invalid dedup review' USING ERRCODE = '22023';
 END IF;

 SELECT c.property_a_id, c.property_b_id INTO prop_a, prop_b
 FROM public.property_dedup_candidates c
 WHERE c.tenant_id = t AND c.id = candidate
 FOR UPDATE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 IF NOT public.actor_can_edit_property(t, prop_a) OR NOT public.actor_can_edit_property(t, prop_b) THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/dedup-review/' || candidate::text, 0));

 next_status := CASE note_outcome
  WHEN 'keep_separate' THEN 'reviewed_keep_separate'
  WHEN 'flag_possible_duplicate' THEN 'reviewed_possible_duplicate'
  ELSE 'reviewed_needs_more_evidence'
 END;

 INSERT INTO public.property_dedup_reviews (
  tenant_id, candidate_id, outcome, reason, recorded_by)
 VALUES (t, candidate, note_outcome, note_reason, actor)
 RETURNING public.property_dedup_reviews.id INTO new_id;

 UPDATE public.property_dedup_candidates
  SET status = next_status
  WHERE tenant_id = t AND id = candidate;

 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type)
 VALUES (t, prop_a, actor, 'dedup.review_recorded');

 RETURN QUERY SELECT r.id, r.tenant_id, r.candidate_id, r.outcome, r.reason,
  r.recorded_by, r.recorded_at, next_status, false, 'none'::text, true
  FROM public.property_dedup_reviews r WHERE r.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.record_property_dedup_review(uuid, uuid, text, text) FROM PUBLIC;

-- No merge helper exists and none is granted. Explicitly refuse common merge names if present.
DO $$
BEGIN
 IF to_regprocedure('public.merge_properties(uuid,uuid,uuid)') IS NOT NULL
  OR to_regprocedure('public.merge_property_records(uuid,uuid,uuid)') IS NOT NULL THEN
  RAISE EXCEPTION 'Property merge helpers must not exist in candidate-only slice';
 END IF;
END $$;

DO $$
BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'oydp_app') THEN
  REVOKE ALL ON TABLE public.property_dedup_candidates FROM oydp_app;
  REVOKE ALL ON TABLE public.property_dedup_reviews FROM oydp_app;
  GRANT SELECT ON TABLE public.property_dedup_candidates TO oydp_app;
  GRANT SELECT ON TABLE public.property_dedup_reviews TO oydp_app;
  GRANT EXECUTE ON FUNCTION public.generate_property_dedup_candidates(uuid) TO oydp_app;
  GRANT EXECUTE ON FUNCTION public.record_property_dedup_review(uuid, uuid, text, text) TO oydp_app;
  REVOKE ALL ON FUNCTION public.reject_property_dedup_rewrite() FROM oydp_app;
  REVOKE ALL ON FUNCTION public.reject_property_dedup_review_rewrite() FROM oydp_app;
  REVOKE ALL ON FUNCTION public.reject_property_dedup_candidate_unsafe_update() FROM oydp_app;
 END IF;
END $$;
