-- Workspace requests and notes. They are untrusted text, not offers, payments,
-- or legal conclusions. Closing a request only changes its workspace status.
CREATE TABLE public.diligence_requests (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 created_by text NOT NULL DEFAULT nullif(current_setting('app.subject_id', true), '')
   CHECK (length(created_by) BETWEEN 1 AND 255),
 title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
 body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 10000),
 status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 closed_at timestamptz,
 UNIQUE (tenant_id, property_id, id),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties (tenant_id, id),
 CHECK ((status='open' AND closed_at IS NULL) OR (status='closed' AND closed_at IS NOT NULL))
);
CREATE INDEX diligence_requests_page_idx ON public.diligence_requests (tenant_id, property_id, created_at DESC, id DESC);
ALTER TABLE public.diligence_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diligence_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY request_read ON public.diligence_requests FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=diligence_requests.tenant_id AND p.id=diligence_requests.property_id)
);
CREATE POLICY request_open ON public.diligence_requests FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND status='open' AND closed_at IS NULL
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=diligence_requests.tenant_id
   AND p.id=diligence_requests.property_id AND p.created_by=diligence_requests.created_by)
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=diligence_requests.tenant_id
   AND m.subject_id=diligence_requests.created_by AND m.role IN ('owner','editor'))
);
CREATE POLICY request_close ON public.diligence_requests FOR UPDATE USING (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND status='open'
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=diligence_requests.tenant_id
   AND p.id=diligence_requests.property_id AND p.created_by=diligence_requests.created_by)
) WITH CHECK (
 status='closed' AND closed_at IS NOT NULL
 AND created_by=nullif(current_setting('app.subject_id', true), '')
);

CREATE TABLE public.diligence_notes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 request_id uuid NOT NULL,
 created_by text NOT NULL DEFAULT nullif(current_setting('app.subject_id', true), '')
   CHECK (length(created_by) BETWEEN 1 AND 255),
 body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 10000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE (tenant_id, property_id, request_id, id),
 FOREIGN KEY (tenant_id, property_id, request_id) REFERENCES public.diligence_requests (tenant_id, property_id, id)
);
CREATE INDEX diligence_notes_page_idx ON public.diligence_notes (tenant_id, property_id, request_id, created_at DESC, id DESC);
ALTER TABLE public.diligence_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diligence_notes FORCE ROW LEVEL SECURITY;
CREATE POLICY note_read ON public.diligence_notes FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=diligence_notes.tenant_id AND p.id=diligence_notes.property_id)
);
CREATE POLICY note_append ON public.diligence_notes FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=diligence_notes.tenant_id AND p.id=diligence_notes.property_id)
 AND EXISTS (SELECT 1 FROM public.diligence_requests r WHERE r.tenant_id=diligence_notes.tenant_id
   AND r.property_id=diligence_notes.property_id AND r.id=diligence_notes.request_id AND r.status='open')
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=diligence_notes.tenant_id
   AND m.subject_id=diligence_notes.created_by)
);

ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events DROP CONSTRAINT access_audit_shape;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK (event_type IN ('property.created','access.granted','access.revoked','claim.recorded',
  'source.recorded','identifier.recorded','identifier.superseded','evidence.recorded',
  'document.stored','document.rejected','diligence.opened','diligence.noted','diligence.closed'));
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type='property.created' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL)
 OR (event_type='access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL)
 OR (event_type='access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL)
 OR (event_type='claim.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NOT NULL)
 OR (event_type IN ('source.recorded','identifier.recorded','identifier.superseded','evidence.recorded',
     'document.stored','document.rejected','diligence.opened','diligence.noted','diligence.closed')
     AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL));
