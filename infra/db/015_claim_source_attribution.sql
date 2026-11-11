-- Optional live evidence_sources citation on unverified user claims.
-- A withdrawn or foreign source cannot be cited. Claim kind and verification_status stay fixed.
-- Writes move through SECURITY DEFINER so the runtime role cannot invent verification.

ALTER TABLE public.property_claims
  ADD COLUMN source_id uuid;
ALTER TABLE public.property_claims
  ADD CONSTRAINT property_claims_source_tenant_fk
  FOREIGN KEY (tenant_id, source_id) REFERENCES public.evidence_sources(tenant_id, id);
CREATE INDEX claims_source_idx ON public.property_claims(tenant_id, source_id)
  WHERE source_id IS NOT NULL;

CREATE FUNCTION public.record_property_claim(t uuid, p uuid, claim_statement text, cited_source uuid)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, created_by text, statement text,
  kind text, verification_status text, source_id uuid, recorded_at timestamptz)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), ''); new_id uuid;
BEGIN
 claim_statement := btrim(claim_statement);
 IF actor IS NULL OR claim_statement IS NULL OR length(claim_statement) NOT BETWEEN 1 AND 10000 THEN
  RAISE EXCEPTION 'Invalid claim' USING ERRCODE = '22023';
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
 INSERT INTO public.property_claims (tenant_id, property_id, statement, source_id)
 VALUES (t, p, claim_statement, cited_source)
 RETURNING public.property_claims.id INTO new_id;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, claim_id)
 VALUES (t, p, actor, 'claim.recorded', new_id);
 RETURN QUERY SELECT c.id, c.tenant_id, c.property_id, c.created_by, c.statement,
  c.kind, c.verification_status, c.source_id, c.recorded_at
  FROM public.property_claims c WHERE c.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.record_property_claim(uuid, uuid, text, uuid) FROM PUBLIC;
