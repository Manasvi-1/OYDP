-- Separate immutable ledger for application-submitted, explicitly UNVERIFIED claims.
-- This does not relabel older evidence assertions or official observations.
CREATE TABLE public.property_claims (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 created_by text NOT NULL DEFAULT nullif(current_setting('app.subject_id',true),'')
   CHECK(length(created_by) BETWEEN 1 AND 255),
 statement text NOT NULL CHECK(length(btrim(statement)) BETWEEN 1 AND 10000),
 kind text NOT NULL DEFAULT 'user_claim' CHECK(kind='user_claim'),
 verification_status text NOT NULL DEFAULT 'unverified' CHECK(verification_status='unverified'),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,property_id,id),
 FOREIGN KEY(tenant_id,property_id) REFERENCES public.properties(tenant_id,id)
);
CREATE INDEX claims_page_idx ON public.property_claims(tenant_id,property_id,recorded_at DESC,id DESC);
CREATE INDEX private_properties_page_idx ON public.properties(tenant_id,created_at DESC,id DESC);
ALTER TABLE public.property_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_claims FORCE ROW LEVEL SECURITY;
CREATE POLICY claim_private_read ON public.property_claims FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS(SELECT 1 FROM public.properties p WHERE p.tenant_id=property_claims.tenant_id AND p.id=property_claims.property_id)
);
CREATE POLICY claim_creator_append ON public.property_claims FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND created_by=nullif(current_setting('app.subject_id',true),'')
 AND EXISTS(SELECT 1 FROM public.properties p WHERE p.tenant_id=property_claims.tenant_id
   AND p.id=property_claims.property_id AND p.created_by=property_claims.created_by)
 AND EXISTS(SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=property_claims.tenant_id
   AND m.subject_id=property_claims.created_by AND m.role IN ('owner','editor'))
);
-- No UPDATE/DELETE policy or runtime privilege; corrections are future append events.
ALTER TABLE public.property_audit_events ADD COLUMN claim_id uuid;
ALTER TABLE public.property_audit_events ADD CONSTRAINT audit_claim_tenant_fk
 FOREIGN KEY(tenant_id,property_id,claim_id) REFERENCES public.property_claims(tenant_id,property_id,id);
ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK(event_type IN ('property.created','access.granted','access.revoked','claim.recorded'));
ALTER TABLE public.property_audit_events DROP CONSTRAINT access_audit_shape;
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type='property.created' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL)
 OR (event_type='access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL)
 OR (event_type='access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL)
 OR (event_type='claim.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NOT NULL));
