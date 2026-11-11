-- Close direct audit forgeability for oydp_app, freeze legacy evidence_assertions writes,
-- restrict source withdrawal to creator or tenant owner, and merge document attribution.

-- Runtime may no longer INSERT into property_audit_events. These helpers own the remaining
-- application-side audit rows that were previously written with a table INSERT grant.
CREATE FUNCTION public.record_property_created_audit(t uuid, p uuid)
 RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id', true), '');
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM 1 FROM public.tenant_memberships
  WHERE tenant_id = t AND subject_id = actor AND role IN ('owner', 'editor') FOR SHARE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM 1 FROM public.properties
  WHERE tenant_id = t AND id = p AND created_by = actor FOR SHARE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type)
 VALUES (t, p, actor, 'property.created');
END $$;
REVOKE ALL ON FUNCTION public.record_property_created_audit(uuid, uuid) FROM PUBLIC;

CREATE FUNCTION public.record_document_quarantined_audit(t uuid, p uuid, d uuid)
 RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id', true), '');
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL THEN
  RAISE EXCEPTION 'Document not found' USING ERRCODE = 'P0002';
 END IF;
 IF NOT public.actor_can_edit_property(t, p) THEN
  RAISE EXCEPTION 'Document not found' USING ERRCODE = 'P0002';
 END IF;
 PERFORM 1 FROM public.property_documents
  WHERE tenant_id = t AND property_id = p AND id = d
    AND created_by = actor AND scan_state = 'quarantined' FOR SHARE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Document not found' USING ERRCODE = 'P0002';
 END IF;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, document_id)
 VALUES (t, p, actor, 'document.quarantined', d);
END $$;
REVOKE ALL ON FUNCTION public.record_document_quarantined_audit(uuid, uuid, uuid) FROM PUBLIC;

CREATE FUNCTION public.record_diligence_audit(t uuid, p uuid, diligence_event text)
 RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id', true), '');
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL
  OR diligence_event IS NULL
  OR diligence_event NOT IN ('diligence.opened', 'diligence.noted', 'diligence.closed') THEN
  RAISE EXCEPTION 'Invalid request' USING ERRCODE = '22023';
 END IF;
 IF diligence_event IN ('diligence.opened', 'diligence.closed') THEN
  PERFORM 1 FROM public.properties
   WHERE tenant_id = t AND id = p AND created_by = actor FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
  PERFORM 1 FROM public.tenant_memberships
   WHERE tenant_id = t AND subject_id = actor AND role IN ('owner', 'editor') FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
 ELSE
  -- Notes may be appended by any current reader while the request is open.
  PERFORM 1 FROM public.properties WHERE tenant_id = t AND id = p FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
  PERFORM 1 FROM public.tenant_memberships WHERE tenant_id = t AND subject_id = actor FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
 END IF;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type)
 VALUES (t, p, actor, diligence_event);
END $$;
REVOKE ALL ON FUNCTION public.record_diligence_audit(uuid, uuid, text) FROM PUBLIC;

-- Source withdrawal: tenant owner may withdraw any source; editors only their own.
CREATE OR REPLACE FUNCTION public.withdraw_evidence_source(t uuid, source uuid, reason text)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
 actor text := nullif(current_setting('app.subject_id', true), '');
 actor_role text;
 source_creator text;
BEGIN
 reason := btrim(reason);
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL
  OR reason IS NULL OR length(reason) NOT BETWEEN 1 AND 500 THEN
  RAISE EXCEPTION 'Invalid source' USING ERRCODE = '22023';
 END IF;
 SELECT role INTO actor_role FROM public.tenant_memberships
  WHERE tenant_id = t AND subject_id = actor AND role IN ('owner', 'editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 SELECT created_by INTO source_creator FROM public.evidence_sources
  WHERE tenant_id = t AND id = source FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 IF actor_role IS DISTINCT FROM 'owner' AND source_creator IS DISTINCT FROM actor THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 UPDATE public.evidence_sources SET withdrawn_at = clock_timestamp(), withdrawal_reason = reason
  WHERE tenant_id = t AND id = source AND withdrawn_at IS NULL;
 IF NOT FOUND THEN RETURN false; END IF;
 INSERT INTO public.tenant_audit_events (tenant_id, actor_subject, event_type, source_id)
 VALUES (t, actor, 'source.withdrawn', source);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.withdraw_evidence_source(uuid, uuid, text) FROM PUBLIC;

-- Attribution: non-null request fields replace; omitted (NULL) fields keep current links.
DROP FUNCTION public.attribute_property_document(uuid, uuid, uuid, uuid, uuid, uuid);

CREATE FUNCTION public.attribute_property_document(
  t uuid, p uuid, d uuid, cited_claim uuid, cited_source uuid, cited_identifier uuid)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, created_by text, media_type text, byte_size integer,
  sha256 bytea, scan_state text, created_at timestamptz, scanned_at timestamptz,
  claim_id uuid, source_id uuid, identifier_id uuid)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
 actor text := nullif(current_setting('app.subject_id', true), '');
 next_claim uuid;
 next_source uuid;
 next_identifier uuid;
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
 SELECT doc.claim_id, doc.source_id, doc.identifier_id
  INTO next_claim, next_source, next_identifier
  FROM public.property_documents doc
  WHERE doc.tenant_id = t AND doc.property_id = p AND doc.id = d FOR UPDATE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Document not found' USING ERRCODE = 'P0002';
 END IF;
 next_claim := COALESCE(cited_claim, next_claim);
 next_source := COALESCE(cited_source, next_source);
 next_identifier := COALESCE(cited_identifier, next_identifier);
 IF next_claim IS NOT NULL THEN
  PERFORM 1 FROM public.property_claims
   WHERE tenant_id = t AND property_id = p AND id = next_claim
     AND kind = 'user_claim' AND verification_status = 'unverified' FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
  END IF;
 END IF;
 IF next_source IS NOT NULL THEN
  PERFORM 1 FROM public.evidence_sources
   WHERE tenant_id = t AND id = next_source AND withdrawn_at IS NULL FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Source is withdrawn' USING ERRCODE = '22023';
  END IF;
 END IF;
 IF next_identifier IS NOT NULL THEN
  PERFORM 1 FROM public.property_identifiers
   WHERE tenant_id = t AND property_id = p AND id = next_identifier
     AND status = 'current' FOR SHARE;
  IF NOT FOUND THEN
   RAISE EXCEPTION 'Invalid attribution' USING ERRCODE = '22023';
  END IF;
 END IF;
 UPDATE public.property_documents
  SET claim_id = next_claim, source_id = next_source, identifier_id = next_identifier
  WHERE tenant_id = t AND property_id = p AND id = d;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, document_id)
 VALUES (t, p, actor, 'document.attributed', d);
 RETURN QUERY SELECT doc.id, doc.tenant_id, doc.property_id, doc.created_by, doc.media_type, doc.byte_size,
  doc.sha256, doc.scan_state, doc.created_at, doc.scanned_at, doc.claim_id, doc.source_id, doc.identifier_id
  FROM public.property_documents doc WHERE doc.id = d;
END $$;
REVOKE ALL ON FUNCTION public.attribute_property_document(uuid, uuid, uuid, uuid, uuid, uuid) FROM PUBLIC;

-- Legacy parallel evidence store: keep readable for inspection, freeze runtime writes.
DROP POLICY IF EXISTS assertion_creator_insert ON public.evidence_assertions;

-- Upgrade path: when oydp_app already exists, close direct audit/assertion DML and grant
-- EXECUTE on helpers created/replaced above. DROP/CREATE of attribute_property_document
-- clears prior EXECUTE grants; new audit helpers never had them. Fresh installs still use
-- scripts/migrate.py --provision-runtime for the full privilege matrix (role may not exist yet).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'oydp_app') THEN
    REVOKE ALL ON TABLE public.property_audit_events FROM oydp_app;
    GRANT SELECT ON TABLE public.property_audit_events TO oydp_app;
    REVOKE ALL ON TABLE public.evidence_assertions FROM oydp_app;
    GRANT SELECT ON TABLE public.evidence_assertions TO oydp_app;
    GRANT EXECUTE ON FUNCTION public.record_property_created_audit(uuid, uuid) TO oydp_app;
    GRANT EXECUTE ON FUNCTION public.record_document_quarantined_audit(uuid, uuid, uuid) TO oydp_app;
    GRANT EXECUTE ON FUNCTION public.record_diligence_audit(uuid, uuid, text) TO oydp_app;
    GRANT EXECUTE ON FUNCTION public.withdraw_evidence_source(uuid, uuid, text) TO oydp_app;
    GRANT EXECUTE ON FUNCTION public.attribute_property_document(uuid, uuid, uuid, uuid, uuid, uuid) TO oydp_app;
  END IF;
END $$;
