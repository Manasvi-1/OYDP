-- Encrypted document quarantine. The runtime role cannot read ciphertext or mark a file clean.
-- scan_state starts at quarantined. pass is possible only through record_document_scan,
-- and only when the same transaction sets app.document_scanner to configured.
CREATE TABLE public.property_documents (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 created_by text NOT NULL CHECK (length(created_by) BETWEEN 1 AND 255),
 media_type text NOT NULL CHECK (media_type IN ('application/pdf','image/png','image/jpeg')),
 byte_size integer NOT NULL CHECK (byte_size BETWEEN 1 AND 1048576),
 sha256 bytea NOT NULL CHECK (octet_length(sha256)=32),
 scan_state text NOT NULL DEFAULT 'quarantined' CHECK (scan_state IN ('quarantined','pass','fail')),
 ciphertext bytea NOT NULL CHECK (octet_length(ciphertext) BETWEEN 17 AND 1048592),
 nonce bytea NOT NULL CHECK (octet_length(nonce)=12),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 scanned_at timestamptz,
 UNIQUE (tenant_id, property_id, id),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties(tenant_id, id),
 CHECK ((scan_state='quarantined' AND scanned_at IS NULL) OR (scan_state IN ('pass','fail') AND scanned_at IS NOT NULL))
);
ALTER TABLE public.property_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_documents FORCE ROW LEVEL SECURITY;
CREATE POLICY document_private_read ON public.property_documents FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=property_documents.tenant_id
  AND p.id=property_documents.property_id)
);
CREATE POLICY document_writer_insert ON public.property_documents FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND created_by=nullif(current_setting('app.subject_id',true),'')
 AND scan_state='quarantined'
 AND scanned_at IS NULL
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=property_documents.tenant_id
  AND m.subject_id=property_documents.created_by AND m.role IN ('owner','editor'))
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=property_documents.tenant_id
  AND p.id=property_documents.property_id AND (
   p.created_by=property_documents.created_by OR EXISTS (
    SELECT 1 FROM public.property_write_grants g WHERE g.tenant_id=p.tenant_id AND g.property_id=p.id
    AND g.subject_id=property_documents.created_by AND NOT g.revoked AND g.expires_at>clock_timestamp())))
);
REVOKE ALL ON public.property_documents FROM PUBLIC;

ALTER TABLE public.property_audit_events ADD COLUMN document_id uuid;
ALTER TABLE public.property_audit_events ADD CONSTRAINT audit_document_tenant_fk
 FOREIGN KEY (tenant_id, property_id, document_id) REFERENCES public.property_documents(tenant_id, property_id, id);
ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK (event_type IN ('property.created','access.granted','access.revoked','claim.recorded','property.corrected','write.granted','write.revoked','document.quarantined','document.scan_passed','document.scan_failed'));
ALTER TABLE public.property_audit_events DROP CONSTRAINT access_audit_shape;
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type='property.created' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL)
 OR (event_type='access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL)
 OR (event_type='access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL)
 OR (event_type='claim.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NOT NULL AND correction_id IS NULL AND document_id IS NULL)
 OR (event_type='property.corrected' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NOT NULL AND document_id IS NULL)
 OR (event_type='write.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL)
 OR (event_type='write.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL)
 OR (event_type IN ('document.quarantined','document.scan_passed','document.scan_failed') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NOT NULL));

CREATE FUNCTION public.record_document_scan(t uuid, p uuid, d uuid, outcome text, digest bytea)
 RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id',true),'');
 current_state text; stored bytea;
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id',true),'')::uuid OR actor IS NULL
 OR outcome IS NULL OR outcome NOT IN ('pass','fail') OR digest IS NULL OR octet_length(digest)<>32 THEN
  RAISE EXCEPTION 'Document scanner unavailable' USING ERRCODE='55000';
 END IF;
 IF outcome='pass' AND current_setting('app.document_scanner', true) IS DISTINCT FROM 'configured' THEN
  RAISE EXCEPTION 'Document scanner unavailable' USING ERRCODE='55000';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id=t AND subject_id=actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/document/' || d::text, 0));
 PERFORM 1 FROM public.properties WHERE tenant_id=t AND id=p AND (
  created_by=actor OR EXISTS (
   SELECT 1 FROM public.property_write_grants g WHERE g.tenant_id=t AND g.property_id=p AND g.subject_id=actor
   AND NOT g.revoked AND g.expires_at>clock_timestamp())) FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002'; END IF;
 SELECT scan_state, sha256 INTO current_state, stored FROM public.property_documents
  WHERE tenant_id=t AND property_id=p AND id=d FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002'; END IF;
 IF current_state IS DISTINCT FROM 'quarantined' THEN
  RAISE EXCEPTION 'Document scan already decided' USING ERRCODE='22023';
 END IF;
 IF stored IS DISTINCT FROM digest THEN
  RAISE EXCEPTION 'Document scanner unavailable' USING ERRCODE='55000';
 END IF;
 UPDATE public.property_documents SET scan_state=outcome, scanned_at=clock_timestamp()
  WHERE tenant_id=t AND property_id=p AND id=d AND scan_state='quarantined';
 IF NOT FOUND THEN RAISE EXCEPTION 'Document scan already decided' USING ERRCODE='22023'; END IF;
 INSERT INTO public.property_audit_events(tenant_id,property_id,actor_subject,event_type,document_id)
 VALUES (t, p, actor, CASE WHEN outcome='pass' THEN 'document.scan_passed' ELSE 'document.scan_failed' END, d);
 RETURN outcome;
END $$;
REVOKE ALL ON FUNCTION public.record_document_scan(uuid,uuid,uuid,text,bytea) FROM PUBLIC;

CREATE FUNCTION public.load_quarantined_document(t uuid, p uuid, d uuid)
 RETURNS TABLE(ciphertext bytea, nonce bytea, media_type text, sha256 bytea, byte_size integer)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id',true),'');
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id',true),'')::uuid OR actor IS NULL THEN
  RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id=t AND subject_id=actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002'; END IF;
 PERFORM 1 FROM public.properties WHERE tenant_id=t AND id=p AND (
  created_by=actor OR EXISTS (
   SELECT 1 FROM public.property_write_grants g WHERE g.tenant_id=t AND g.property_id=p AND g.subject_id=actor
   AND NOT g.revoked AND g.expires_at>clock_timestamp())) FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002'; END IF;
 SELECT doc.ciphertext, doc.nonce, doc.media_type, doc.sha256, doc.byte_size
  INTO ciphertext, nonce, media_type, sha256, byte_size
  FROM public.property_documents doc
  WHERE doc.tenant_id=t AND doc.property_id=p AND doc.id=d AND doc.scan_state='quarantined';
 IF NOT FOUND THEN RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002'; END IF;
 RETURN NEXT;
END $$;
REVOKE ALL ON FUNCTION public.load_quarantined_document(uuid,uuid,uuid) FROM PUBLIC;

CREATE FUNCTION public.load_document_ciphertext(t uuid, p uuid, d uuid)
 RETURNS TABLE(ciphertext bytea, nonce bytea, media_type text, sha256 bytea, byte_size integer)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id',true),'');
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id',true),'')::uuid OR actor IS NULL THEN
  RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id=t AND subject_id=actor FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002'; END IF;
 PERFORM 1 FROM public.properties WHERE tenant_id=t AND id=p AND (
  created_by=actor OR EXISTS (
   SELECT 1 FROM public.property_read_grants g WHERE g.tenant_id=t AND g.property_id=p AND g.subject_id=actor
   AND NOT g.revoked AND g.expires_at>clock_timestamp())) FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002'; END IF;
 IF NOT EXISTS (SELECT 1 FROM public.property_documents doc WHERE doc.tenant_id=t AND doc.property_id=p AND doc.id=d) THEN
  RAISE EXCEPTION 'Document not found' USING ERRCODE='P0002';
 END IF;
 SELECT doc.ciphertext, doc.nonce, doc.media_type, doc.sha256, doc.byte_size
  INTO ciphertext, nonce, media_type, sha256, byte_size
  FROM public.property_documents doc
  WHERE doc.tenant_id=t AND doc.property_id=p AND doc.id=d AND doc.scan_state='pass';
 IF NOT FOUND THEN RAISE EXCEPTION 'Document is not available' USING ERRCODE='42501'; END IF;
 RETURN NEXT;
END $$;
REVOKE ALL ON FUNCTION public.load_document_ciphertext(uuid,uuid,uuid) FROM PUBLIC;
