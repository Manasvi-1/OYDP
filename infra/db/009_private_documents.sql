-- Private document metadata. Bytes stay outside the database, encrypted by the
-- application. status is fixed at insert: clean files passed the content gate,
-- rejected rows record the attempt and have no stored bytes. Runtime cannot
-- update either outcome. This is not a certified malware scan.
CREATE TABLE public.property_documents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 created_by text NOT NULL DEFAULT nullif(current_setting('app.subject_id', true), '')
   CHECK (length(created_by) BETWEEN 1 AND 255),
 sha256 bytea NOT NULL CHECK (octet_length(sha256) = 32),
 byte_size integer NOT NULL CHECK (byte_size BETWEEN 1 AND 10485760),
 media_type text CHECK (media_type IS NULL OR media_type IN ('application/pdf','image/png','image/jpeg')),
 status text NOT NULL CHECK (status IN ('rejected','clean')),
 rejection_code text CHECK (rejection_code IS NULL OR rejection_code IN ('empty','size','type','active')),
 encryption_nonce bytea CHECK (encryption_nonce IS NULL OR octet_length(encryption_nonce) = 12),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE (tenant_id, property_id, id),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties (tenant_id, id),
 CHECK ((status='clean' AND media_type IS NOT NULL AND encryption_nonce IS NOT NULL AND rejection_code IS NULL)
     OR (status='rejected' AND media_type IS NULL AND encryption_nonce IS NULL AND rejection_code IS NOT NULL))
);
CREATE INDEX documents_page_idx ON public.property_documents (tenant_id, property_id, created_at DESC, id DESC);
ALTER TABLE public.property_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_documents FORCE ROW LEVEL SECURITY;
CREATE POLICY document_creator_read ON public.property_documents FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=property_documents.tenant_id
   AND p.id=property_documents.property_id AND p.created_by=property_documents.created_by)
);
CREATE POLICY document_creator_append ON public.property_documents FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=property_documents.tenant_id
   AND p.id=property_documents.property_id AND p.created_by=property_documents.created_by)
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=property_documents.tenant_id
   AND m.subject_id=property_documents.created_by AND m.role IN ('owner','editor'))
);

ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events DROP CONSTRAINT access_audit_shape;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK (event_type IN ('property.created','access.granted','access.revoked','claim.recorded',
  'source.recorded','identifier.recorded','identifier.superseded','evidence.recorded',
  'document.stored','document.rejected'));
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type='property.created' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL)
 OR (event_type='access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL)
 OR (event_type='access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL)
 OR (event_type='claim.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NOT NULL)
 OR (event_type IN ('source.recorded','identifier.recorded','identifier.superseded','evidence.recorded','document.stored','document.rejected')
     AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL));
