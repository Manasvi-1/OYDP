-- Optional review↔claim citation alongside the existing live source citation.
-- Only an unverified user_claim on the same property may be cited.
-- Replaces record_professional_review with a six-argument form; title_effect stays none.

ALTER TABLE public.professional_reviews
  ADD COLUMN claim_id uuid;
ALTER TABLE public.professional_reviews
  ADD CONSTRAINT professional_reviews_claim_tenant_fk
  FOREIGN KEY (tenant_id, property_id, claim_id)
  REFERENCES public.property_claims(tenant_id, property_id, id);
CREATE INDEX reviews_claim_idx ON public.professional_reviews(tenant_id, property_id, claim_id)
  WHERE claim_id IS NOT NULL;

DROP FUNCTION public.record_professional_review(uuid, uuid, text, text, uuid);

CREATE FUNCTION public.record_professional_review(
  t uuid, p uuid, review_disposition text, review_statement text, cited_source uuid, cited_claim uuid)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, reviewer_subject text, disposition text,
  statement text, source_id uuid, claim_id uuid, recorded_at timestamptz)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), ''); new_id uuid;
BEGIN
 review_statement := btrim(review_statement);
 IF actor IS NULL OR review_disposition IS NULL OR review_disposition NOT IN ('recorded','abstained')
  OR review_statement IS NULL OR length(review_statement) NOT BETWEEN 1 AND 2000 THEN
  RAISE EXCEPTION 'Invalid review' USING ERRCODE = '22023';
 END IF;
 IF NOT public.actor_can_edit_property(t, p) THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 IF cited_source IS NOT NULL THEN
  PERFORM 1 FROM public.evidence_sources
   WHERE tenant_id = t AND id = cited_source AND withdrawn_at IS NULL FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Source is withdrawn' USING ERRCODE = '22023';
  END IF;
 END IF;
 IF cited_claim IS NOT NULL THEN
  PERFORM 1 FROM public.property_claims
   WHERE tenant_id = t AND property_id = p AND id = cited_claim
     AND kind = 'user_claim' AND verification_status = 'unverified' FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
  END IF;
 END IF;
 INSERT INTO public.professional_reviews (
  tenant_id, property_id, reviewer_subject, disposition, statement, source_id, claim_id)
 VALUES (t, p, actor, review_disposition, review_statement, cited_source, cited_claim)
 RETURNING public.professional_reviews.id INTO new_id;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, review_id)
 VALUES (t, p, actor, 'review.recorded', new_id);
 RETURN QUERY SELECT r.id, r.tenant_id, r.property_id, r.reviewer_subject, r.disposition,
  r.statement, r.source_id, r.claim_id, r.recorded_at
  FROM public.professional_reviews r WHERE r.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.record_professional_review(uuid, uuid, text, text, uuid, uuid) FROM PUBLIC;
