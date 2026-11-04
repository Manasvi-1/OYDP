-- Versioned identifiers, property-scoped source notes, and assertion review labels.
-- review_status and source_class are workspace labels. They are not title findings,
-- professional licences, or official observations. Runtime cannot insert official_observation.
CREATE TABLE public.evidence_sources (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
 source_class text NOT NULL CHECK (source_class IN ('user_supplied','professional_note','published_reference')),
 locator text CHECK (locator IS NULL OR length(btrim(locator)) BETWEEN 1 AND 500),
 created_by text NOT NULL DEFAULT nullif(current_setting('app.subject_id', true), '')
   CHECK (length(created_by) BETWEEN 1 AND 255),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE (tenant_id, property_id, id),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties (tenant_id, id)
);
CREATE INDEX sources_page_idx ON public.evidence_sources (tenant_id, property_id, recorded_at DESC, id DESC);
ALTER TABLE public.evidence_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_sources FORCE ROW LEVEL SECURITY;
CREATE POLICY source_private_read ON public.evidence_sources FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=evidence_sources.tenant_id AND p.id=evidence_sources.property_id)
);
CREATE POLICY source_creator_append ON public.evidence_sources FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=evidence_sources.tenant_id
   AND p.id=evidence_sources.property_id AND p.created_by=evidence_sources.created_by)
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=evidence_sources.tenant_id
   AND m.subject_id=evidence_sources.created_by AND m.role IN ('owner','editor'))
);

CREATE TABLE public.property_identifiers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 scheme text NOT NULL CHECK (scheme IN ('local_label','survey_number','khata','municipal_reference')),
 identifier_value text NOT NULL CHECK (length(btrim(identifier_value)) BETWEEN 1 AND 200),
 created_by text NOT NULL DEFAULT nullif(current_setting('app.subject_id', true), '')
   CHECK (length(created_by) BETWEEN 1 AND 255),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 superseded_at timestamptz,
 UNIQUE (tenant_id, property_id, id),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties (tenant_id, id)
);
CREATE UNIQUE INDEX property_identifiers_one_current ON public.property_identifiers (tenant_id, property_id, scheme)
 WHERE superseded_at IS NULL;
CREATE INDEX identifiers_page_idx ON public.property_identifiers (tenant_id, property_id, recorded_at DESC, id DESC);
ALTER TABLE public.property_identifiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_identifiers FORCE ROW LEVEL SECURITY;
CREATE POLICY identifier_private_read ON public.property_identifiers FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=property_identifiers.tenant_id AND p.id=property_identifiers.property_id)
);
CREATE POLICY identifier_creator_append ON public.property_identifiers FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND superseded_at IS NULL
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=property_identifiers.tenant_id
   AND p.id=property_identifiers.property_id AND p.created_by=property_identifiers.created_by)
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=property_identifiers.tenant_id
   AND m.subject_id=property_identifiers.created_by AND m.role IN ('owner','editor'))
);
CREATE POLICY identifier_supersede ON public.property_identifiers FOR UPDATE USING (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND superseded_at IS NULL
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=property_identifiers.tenant_id
   AND p.id=property_identifiers.property_id AND p.created_by=property_identifiers.created_by)
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=property_identifiers.tenant_id
   AND m.subject_id=property_identifiers.created_by AND m.role IN ('owner','editor'))
) WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND superseded_at IS NOT NULL
 AND created_by=nullif(current_setting('app.subject_id', true), '')
);

ALTER TABLE public.evidence_assertions ADD COLUMN created_by text
 CHECK (created_by IS NULL OR length(created_by) BETWEEN 1 AND 255);
ALTER TABLE public.evidence_assertions ALTER COLUMN created_by
 SET DEFAULT nullif(current_setting('app.subject_id', true), '');
ALTER TABLE public.evidence_assertions ADD COLUMN source_id uuid;
ALTER TABLE public.evidence_assertions ADD COLUMN review_status text NOT NULL DEFAULT 'unreviewed'
 CHECK (review_status IN ('unreviewed','recorded'));
ALTER TABLE public.evidence_assertions ADD CONSTRAINT evidence_source_fk
 FOREIGN KEY (tenant_id, property_id, source_id) REFERENCES public.evidence_sources (tenant_id, property_id, id);
CREATE INDEX evidence_page_idx ON public.evidence_assertions (tenant_id, property_id, created_at DESC, id DESC);
DROP POLICY assertion_creator_insert ON public.evidence_assertions;
CREATE POLICY assertion_creator_insert ON public.evidence_assertions FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND source_kind IN ('user_claim','professional_review')
 AND created_by=nullif(current_setting('app.subject_id', true), '')
 AND (
   (source_kind='user_claim' AND review_status='unreviewed')
   OR (source_kind='professional_review' AND review_status='recorded' AND source_reference IS NOT NULL AND length(btrim(source_reference)) BETWEEN 1 AND 500)
 )
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=evidence_assertions.tenant_id
   AND p.id=evidence_assertions.property_id AND p.created_by=evidence_assertions.created_by)
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=evidence_assertions.tenant_id
   AND m.subject_id=evidence_assertions.created_by AND m.role IN ('owner','editor'))
);

ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events DROP CONSTRAINT access_audit_shape;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK (event_type IN ('property.created','access.granted','access.revoked','claim.recorded',
  'source.recorded','identifier.recorded','identifier.superseded','evidence.recorded'));
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type='property.created' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL)
 OR (event_type='access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL)
 OR (event_type='access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL)
 OR (event_type='claim.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NOT NULL)
 OR (event_type IN ('source.recorded','identifier.recorded','identifier.superseded','evidence.recorded')
     AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL));
