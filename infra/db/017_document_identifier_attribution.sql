-- Optional document↔identifier attribution alongside claim/source links.
-- Only a current identifier on the same property may be cited.
-- Replaces attribute_property_document with a six-argument form; export packets keep title_verified false.

ALTER TABLE public.property_documents
  ADD COLUMN identifier_id uuid;
ALTER TABLE public.property_documents
  ADD CONSTRAINT property_documents_identifier_tenant_fk
  FOREIGN KEY (tenant_id, property_id, identifier_id)
  REFERENCES public.property_identifiers(tenant_id, property_id, id);
CREATE INDEX documents_identifier_idx ON public.property_documents(tenant_id, property_id, identifier_id)
  WHERE identifier_id IS NOT NULL;

DROP FUNCTION public.attribute_property_document(uuid, uuid, uuid, uuid, uuid);

CREATE FUNCTION public.attribute_property_document(
  t uuid, p uuid, d uuid, cited_claim uuid, cited_source uuid, cited_identifier uuid)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, created_by text, media_type text, byte_size integer,
  sha256 bytea, scan_state text, created_at timestamptz, scanned_at timestamptz,
  claim_id uuid, source_id uuid, identifier_id uuid)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), '');
BEGIN
 IF actor IS NULL THEN
  RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
 END IF;
 IF cited_claim IS NULL AND cited_source IS NULL AND cited_identifier IS NULL THEN
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
 IF cited_identifier IS NOT NULL THEN
  PERFORM 1 FROM public.property_identifiers
   WHERE tenant_id = t AND property_id = p AND id = cited_identifier
     AND status = 'current' FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
  END IF;
 END IF;
 UPDATE public.property_documents
  SET claim_id = cited_claim, source_id = cited_source, identifier_id = cited_identifier
  WHERE tenant_id = t AND property_id = p AND id = d;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, document_id)
 VALUES (t, p, actor, 'document.attributed', d);
 RETURN QUERY SELECT doc.id, doc.tenant_id, doc.property_id, doc.created_by, doc.media_type, doc.byte_size,
  doc.sha256, doc.scan_state, doc.created_at, doc.scanned_at, doc.claim_id, doc.source_id, doc.identifier_id
  FROM public.property_documents doc WHERE doc.id = d;
END $$;
REVOKE ALL ON FUNCTION public.attribute_property_document(uuid, uuid, uuid, uuid, uuid, uuid) FROM PUBLIC;
