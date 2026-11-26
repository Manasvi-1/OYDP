-- Append-only human dispositions for unresolved evidence signals.
-- A disposition does not clear identifier conflict status, change claim
-- verification_status, merge properties, or assert title or ownership.
-- Follows 021_membership_session_posture.sql.

ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK (event_type IN (
  'property.created','access.granted','access.revoked','claim.recorded','property.corrected',
  'write.granted','write.revoked','document.quarantined','document.scan_passed','document.scan_failed',
  'document.attributed',
  'identifier.recorded','identifier.conflict','review.recorded','consent.recorded','consent.revoked','packet.exported',
  'diligence.opened','diligence.noted','diligence.closed',
  'conflict.disposition_recorded'));
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
 OR (event_type IN ('diligence.opened','diligence.noted','diligence.closed','conflict.disposition_recorded') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL));

CREATE TABLE public.evidence_conflict_dispositions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 signal_kind text NOT NULL CHECK (signal_kind IN (
  'identifier_conflict',
  'withdrawn_claim_citation',
  'withdrawn_document_citation',
  'withdrawn_review_citation')),
 signal_id uuid NOT NULL,
 outcome text NOT NULL CHECK (outcome IN ('noted', 'kept_unresolved')),
 reason text NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 500),
 recorded_by text NOT NULL CHECK (length(recorded_by) BETWEEN 1 AND 255),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties (tenant_id, id)
);
CREATE INDEX evidence_conflict_dispositions_page_idx
 ON public.evidence_conflict_dispositions (tenant_id, property_id, recorded_at DESC, id DESC);
ALTER TABLE public.evidence_conflict_dispositions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_conflict_dispositions FORCE ROW LEVEL SECURITY;
CREATE POLICY evidence_conflict_disposition_read ON public.evidence_conflict_dispositions FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (
  SELECT 1 FROM public.properties p
  WHERE p.tenant_id = evidence_conflict_dispositions.tenant_id
    AND p.id = evidence_conflict_dispositions.property_id)
);
REVOKE ALL ON public.evidence_conflict_dispositions FROM PUBLIC;

CREATE FUNCTION public.reject_evidence_conflict_disposition_rewrite()
 RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
 RAISE EXCEPTION 'Evidence conflict dispositions are append-only' USING ERRCODE = '42501';
END $$;
REVOKE ALL ON FUNCTION public.reject_evidence_conflict_disposition_rewrite() FROM PUBLIC;
CREATE TRIGGER evidence_conflict_dispositions_no_update
 BEFORE UPDATE OR DELETE ON public.evidence_conflict_dispositions
 FOR EACH ROW EXECUTE FUNCTION public.reject_evidence_conflict_disposition_rewrite();
CREATE TRIGGER evidence_conflict_dispositions_no_truncate
 BEFORE TRUNCATE ON public.evidence_conflict_dispositions
 FOR EACH STATEMENT EXECUTE FUNCTION public.reject_evidence_conflict_disposition_rewrite();

CREATE FUNCTION public.record_evidence_conflict_disposition(
  t uuid, p uuid, kind text, signal uuid, note_outcome text, note_reason text)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, signal_kind text, signal_id uuid,
  outcome text, reason text, recorded_by text, recorded_at timestamptz,
  title_effect text, verification_unchanged boolean)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
 actor text := nullif(current_setting('app.subject_id', true), '');
 new_id uuid;
BEGIN
 note_reason := btrim(note_reason);
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL
  OR kind IS NULL OR kind NOT IN (
    'identifier_conflict',
    'withdrawn_claim_citation',
    'withdrawn_document_citation',
    'withdrawn_review_citation')
  OR signal IS NULL
  OR note_outcome IS NULL OR note_outcome NOT IN ('noted', 'kept_unresolved')
  OR note_reason IS NULL OR length(note_reason) NOT BETWEEN 1 AND 500
  OR note_reason ~ '[[:cntrl:]]' THEN
  RAISE EXCEPTION 'Invalid conflict disposition' USING ERRCODE = '22023';
 END IF;
 IF NOT public.actor_can_edit_property(t, p) THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/conflict-disposition/' || p::text, 0));

 IF kind = 'identifier_conflict' THEN
  PERFORM 1 FROM public.property_identifiers i
   WHERE i.tenant_id = t AND i.property_id = p AND i.id = signal AND i.status = 'conflict'
   FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid conflict disposition' USING ERRCODE = '22023';
  END IF;
 ELSIF kind = 'withdrawn_claim_citation' THEN
  PERFORM 1 FROM public.property_claims c
   JOIN public.evidence_sources s ON s.tenant_id = c.tenant_id AND s.id = c.source_id
   WHERE c.tenant_id = t AND c.property_id = p AND c.id = signal
     AND c.kind = 'user_claim' AND c.verification_status = 'unverified'
     AND c.source_id IS NOT NULL AND s.withdrawn_at IS NOT NULL
   FOR SHARE OF c;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid conflict disposition' USING ERRCODE = '22023';
  END IF;
 ELSIF kind = 'withdrawn_document_citation' THEN
  PERFORM 1 FROM public.property_documents d
   JOIN public.evidence_sources s ON s.tenant_id = d.tenant_id AND s.id = d.source_id
   WHERE d.tenant_id = t AND d.property_id = p AND d.id = signal
     AND d.source_id IS NOT NULL AND s.withdrawn_at IS NOT NULL
   FOR SHARE OF d;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid conflict disposition' USING ERRCODE = '22023';
  END IF;
 ELSE
  PERFORM 1 FROM public.professional_reviews r
   JOIN public.evidence_sources s ON s.tenant_id = r.tenant_id AND s.id = r.source_id
   WHERE r.tenant_id = t AND r.property_id = p AND r.id = signal
     AND r.source_id IS NOT NULL AND s.withdrawn_at IS NOT NULL
   FOR SHARE OF r;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid conflict disposition' USING ERRCODE = '22023';
  END IF;
 END IF;

 INSERT INTO public.evidence_conflict_dispositions (
  tenant_id, property_id, signal_kind, signal_id, outcome, reason, recorded_by)
 VALUES (t, p, kind, signal, note_outcome, note_reason, actor)
 RETURNING public.evidence_conflict_dispositions.id INTO new_id;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type)
 VALUES (t, p, actor, 'conflict.disposition_recorded');
 RETURN QUERY SELECT d.id, d.tenant_id, d.property_id, d.signal_kind, d.signal_id,
  d.outcome, d.reason, d.recorded_by, d.recorded_at, 'none'::text, true
  FROM public.evidence_conflict_dispositions d WHERE d.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.record_evidence_conflict_disposition(uuid, uuid, text, uuid, text, text) FROM PUBLIC;

-- Fresh installs create oydp_app in provision_runtime after migrations.
-- Re-applying on a database that already has the role still closes direct writes.
DO $$
BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'oydp_app') THEN
  REVOKE ALL ON TABLE public.evidence_conflict_dispositions FROM oydp_app;
  GRANT SELECT ON TABLE public.evidence_conflict_dispositions TO oydp_app;
  GRANT EXECUTE ON FUNCTION public.record_evidence_conflict_disposition(uuid, uuid, text, uuid, text, text) TO oydp_app;
  REVOKE ALL ON FUNCTION public.reject_evidence_conflict_disposition_rewrite() FROM oydp_app;
 END IF;
END $$;
