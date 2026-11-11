-- Optional review↔document and review↔identifier citations.
-- Document must belong to the same property. Identifier must be current on that property.
-- Replaces record_professional_review with an eight-argument form; title_effect stays none.

ALTER TABLE public.professional_reviews
  ADD COLUMN document_id uuid,
  ADD COLUMN identifier_id uuid;
ALTER TABLE public.professional_reviews
  ADD CONSTRAINT professional_reviews_document_tenant_fk
  FOREIGN KEY (tenant_id, property_id, document_id)
  REFERENCES public.property_documents(tenant_id, property_id, id);
ALTER TABLE public.professional_reviews
  ADD CONSTRAINT professional_reviews_identifier_tenant_fk
  FOREIGN KEY (tenant_id, property_id, identifier_id)
  REFERENCES public.property_identifiers(tenant_id, property_id, id);
CREATE INDEX reviews_document_idx ON public.professional_reviews(tenant_id, property_id, document_id)
  WHERE document_id IS NOT NULL;
CREATE INDEX reviews_identifier_idx ON public.professional_reviews(tenant_id, property_id, identifier_id)
  WHERE identifier_id IS NOT NULL;

DROP FUNCTION public.record_professional_review(uuid, uuid, text, text, uuid, uuid);

CREATE FUNCTION public.record_professional_review(
  t uuid, p uuid, review_disposition text, review_statement text,
  cited_source uuid, cited_claim uuid, cited_document uuid, cited_identifier uuid)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, reviewer_subject text, disposition text,
  statement text, source_id uuid, claim_id uuid, document_id uuid, identifier_id uuid,
  recorded_at timestamptz)
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
 IF cited_document IS NOT NULL THEN
  PERFORM 1 FROM public.property_documents
   WHERE tenant_id = t AND property_id = p AND id = cited_document FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
  END IF;
 END IF;
 IF cited_identifier IS NOT NULL THEN
  PERFORM 1 FROM public.property_identifiers
   WHERE tenant_id = t AND property_id = p AND id = cited_identifier
     AND status = 'current' FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
  END IF;
 END IF;
 INSERT INTO public.professional_reviews (
  tenant_id, property_id, reviewer_subject, disposition, statement,
  source_id, claim_id, document_id, identifier_id)
 VALUES (t, p, actor, review_disposition, review_statement,
  cited_source, cited_claim, cited_document, cited_identifier)
 RETURNING public.professional_reviews.id INTO new_id;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, review_id)
 VALUES (t, p, actor, 'review.recorded', new_id);
 RETURN QUERY SELECT r.id, r.tenant_id, r.property_id, r.reviewer_subject, r.disposition,
  r.statement, r.source_id, r.claim_id, r.document_id, r.identifier_id, r.recorded_at
  FROM public.professional_reviews r WHERE r.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.record_professional_review(uuid, uuid, text, text, uuid, uuid, uuid, uuid) FROM PUBLIC;
