-- Optional document↔claim and document↔source attribution on quarantined files.
-- Attribution never marks a claim verified or a source rights-known.
-- Runtime cannot UPDATE document rows directly; only attribute_property_document may set links.

ALTER TABLE public.property_documents
  ADD COLUMN claim_id uuid,
  ADD COLUMN source_id uuid;
ALTER TABLE public.property_documents
  ADD CONSTRAINT property_documents_claim_tenant_fk
  FOREIGN KEY (tenant_id, property_id, claim_id)
  REFERENCES public.property_claims(tenant_id, property_id, id);
ALTER TABLE public.property_documents
  ADD CONSTRAINT property_documents_source_tenant_fk
  FOREIGN KEY (tenant_id, source_id)
  REFERENCES public.evidence_sources(tenant_id, id);
CREATE INDEX documents_claim_idx ON public.property_documents(tenant_id, property_id, claim_id)
  WHERE claim_id IS NOT NULL;
CREATE INDEX documents_source_idx ON public.property_documents(tenant_id, source_id)
  WHERE source_id IS NOT NULL;

ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK (event_type IN (
  'property.created','access.granted','access.revoked','claim.recorded','property.corrected',
  'write.granted','write.revoked','document.quarantined','document.scan_passed','document.scan_failed',
  'document.attributed',
  'identifier.recorded','identifier.conflict','review.recorded','consent.recorded','consent.revoked','packet.exported',
  'diligence.opened','diligence.noted','diligence.closed'));
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
 OR (event_type IN ('diligence.opened','diligence.noted','diligence.closed') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL));

CREATE FUNCTION public.attribute_property_document(t uuid, p uuid, d uuid, cited_claim uuid, cited_source uuid)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, created_by text, media_type text, byte_size integer,
  sha256 bytea, scan_state text, created_at timestamptz, scanned_at timestamptz,
  claim_id uuid, source_id uuid)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), '');
BEGIN
 IF actor IS NULL THEN
  RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
 END IF;
 IF cited_claim IS NULL AND cited_source IS NULL THEN
  RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
 END IF;
 IF NOT public.actor_can_edit_property(t, p) THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM 1 FROM public.property_documents
  WHERE tenant_id = t AND property_id = p AND id = d FOR UPDATE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Document not found' USING ERRCODE = 'P0002';
 END IF;
 IF cited_claim IS NOT NULL THEN
  PERFORM 1 FROM public.property_claims
   WHERE tenant_id = t AND property_id = p AND id = cited_claim
     AND kind = 'user_claim' AND verification_status = 'unverified' FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
  END IF;
 END IF;
 IF cited_source IS NOT NULL THEN
  PERFORM 1 FROM public.evidence_sources
   WHERE tenant_id = t AND id = cited_source AND withdrawn_at IS NULL FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Source is withdrawn' USING ERRCODE = '22023';
  END IF;
 END IF;
 UPDATE public.property_documents
  SET claim_id = cited_claim, source_id = cited_source
  WHERE tenant_id = t AND property_id = p AND id = d;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, document_id)
 VALUES (t, p, actor, 'document.attributed', d);
 RETURN QUERY SELECT doc.id, doc.tenant_id, doc.property_id, doc.created_by, doc.media_type, doc.byte_size,
  doc.sha256, doc.scan_state, doc.created_at, doc.scanned_at, doc.claim_id, doc.source_id
  FROM public.property_documents doc WHERE doc.id = d;
END $$;
REVOKE ALL ON FUNCTION public.attribute_property_document(uuid, uuid, uuid, uuid, uuid) FROM PUBLIC;
