-- Trusted evidence for one private property.
-- Identifiers keep history. A professional review is recorded or abstained and never becomes title.
-- Sources stay rights-unknown. Export requires a live creator consent.
-- property_audit_events is copied into audit_ledger in the same transaction.
-- The ledger rejects updates, deletes, truncation, and rows that do not match an outbox event.
-- A database superuser can still disable triggers. This is not an external write-once store.

CREATE TABLE public.property_identifiers (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 scheme text NOT NULL CHECK (scheme IN ('internal','survey','municipal','khata')),
 identifier_value text NOT NULL CHECK (length(identifier_value) BETWEEN 1 AND 120 AND identifier_value !~ '[[:cntrl:]]'),
 version integer NOT NULL CHECK (version >= 1),
 status text NOT NULL CHECK (status IN ('current','superseded','conflict')),
 recorded_by text NOT NULL CHECK (length(recorded_by) BETWEEN 1 AND 255),
 related_id uuid,
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE (tenant_id, property_id, id),
 UNIQUE (tenant_id, property_id, scheme, version),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties(tenant_id, id),
 FOREIGN KEY (tenant_id, property_id, related_id) REFERENCES public.property_identifiers(tenant_id, property_id, id)
);
CREATE UNIQUE INDEX property_identifiers_one_current
 ON public.property_identifiers(tenant_id, property_id, scheme) WHERE status = 'current';
CREATE INDEX identifiers_page_idx
 ON public.property_identifiers(tenant_id, property_id, recorded_at DESC, id DESC);
ALTER TABLE public.property_identifiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_identifiers FORCE ROW LEVEL SECURITY;
CREATE POLICY identifier_private_read ON public.property_identifiers FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id = property_identifiers.tenant_id
  AND p.id = property_identifiers.property_id)
);
REVOKE ALL ON public.property_identifiers FROM PUBLIC;

CREATE TABLE public.evidence_sources (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
 origin text NOT NULL CHECK (origin IN ('user_supplied','professional','published_notice')),
 jurisdiction text NOT NULL CHECK (length(jurisdiction) BETWEEN 1 AND 100),
 rights_status text NOT NULL DEFAULT 'unknown' CHECK (rights_status = 'unknown'),
 created_by text NOT NULL CHECK (length(created_by) BETWEEN 1 AND 255),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 withdrawn_at timestamptz,
 withdrawal_reason text CHECK (withdrawal_reason IS NULL OR length(withdrawal_reason) BETWEEN 1 AND 500),
 UNIQUE (tenant_id, id),
 CHECK ((withdrawn_at IS NULL AND withdrawal_reason IS NULL) OR (withdrawn_at IS NOT NULL AND withdrawal_reason IS NOT NULL))
);
CREATE INDEX sources_page_idx ON public.evidence_sources(tenant_id, created_at DESC, id DESC);
ALTER TABLE public.evidence_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_sources FORCE ROW LEVEL SECURITY;
CREATE POLICY source_tenant_read ON public.evidence_sources FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id = evidence_sources.tenant_id
  AND m.subject_id = nullif(current_setting('app.subject_id', true), ''))
);
REVOKE ALL ON public.evidence_sources FROM PUBLIC;

CREATE TABLE public.professional_reviews (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 reviewer_subject text NOT NULL CHECK (length(reviewer_subject) BETWEEN 1 AND 255),
 disposition text NOT NULL CHECK (disposition IN ('recorded','abstained')),
 statement text NOT NULL CHECK (length(statement) BETWEEN 1 AND 2000),
 source_id uuid,
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE (tenant_id, property_id, id),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties(tenant_id, id),
 FOREIGN KEY (tenant_id, source_id) REFERENCES public.evidence_sources(tenant_id, id)
);
CREATE INDEX reviews_page_idx ON public.professional_reviews(tenant_id, property_id, recorded_at DESC, id DESC);
ALTER TABLE public.professional_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.professional_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY review_private_read ON public.professional_reviews FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id = professional_reviews.tenant_id
  AND p.id = professional_reviews.property_id)
);
REVOKE ALL ON public.professional_reviews FROM PUBLIC;

CREATE TABLE public.property_consents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 subject_id text NOT NULL CHECK (length(subject_id) BETWEEN 1 AND 255),
 purpose text NOT NULL CHECK (purpose = 'passport_export'),
 granted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 revoked_at timestamptz,
 UNIQUE (tenant_id, property_id, id),
 FOREIGN KEY (tenant_id, property_id) REFERENCES public.properties(tenant_id, id),
 CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);
CREATE UNIQUE INDEX property_consents_one_live
 ON public.property_consents(tenant_id, property_id, purpose) WHERE revoked_at IS NULL;
CREATE INDEX consents_page_idx ON public.property_consents(tenant_id, property_id, granted_at DESC, id DESC);
ALTER TABLE public.property_consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_consents FORCE ROW LEVEL SECURITY;
CREATE POLICY consent_private_read ON public.property_consents FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id = property_consents.tenant_id
  AND p.id = property_consents.property_id)
);
REVOKE ALL ON public.property_consents FROM PUBLIC;

CREATE INDEX documents_page_idx ON public.property_documents(tenant_id, property_id, created_at DESC, id DESC);

ALTER TABLE public.property_audit_events ADD COLUMN identifier_id uuid;
ALTER TABLE public.property_audit_events ADD COLUMN review_id uuid;
ALTER TABLE public.property_audit_events ADD COLUMN consent_id uuid;
ALTER TABLE public.property_audit_events ADD CONSTRAINT audit_identifier_tenant_fk
 FOREIGN KEY (tenant_id, property_id, identifier_id) REFERENCES public.property_identifiers(tenant_id, property_id, id);
ALTER TABLE public.property_audit_events ADD CONSTRAINT audit_review_tenant_fk
 FOREIGN KEY (tenant_id, property_id, review_id) REFERENCES public.professional_reviews(tenant_id, property_id, id);
ALTER TABLE public.property_audit_events ADD CONSTRAINT audit_consent_tenant_fk
 FOREIGN KEY (tenant_id, property_id, consent_id) REFERENCES public.property_consents(tenant_id, property_id, id);
ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK (event_type IN (
  'property.created','access.granted','access.revoked','claim.recorded','property.corrected',
  'write.granted','write.revoked','document.quarantined','document.scan_passed','document.scan_failed',
  'identifier.recorded','identifier.conflict','review.recorded','consent.recorded','consent.revoked','packet.exported'));
ALTER TABLE public.property_audit_events DROP CONSTRAINT access_audit_shape;
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type = 'property.created' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'claim.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NOT NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'property.corrected' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NOT NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'write.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'write.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type IN ('document.quarantined','document.scan_passed','document.scan_failed') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NOT NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type IN ('identifier.recorded','identifier.conflict') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NOT NULL AND review_id IS NULL AND consent_id IS NULL)
 OR (event_type = 'review.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NOT NULL AND consent_id IS NULL)
 OR (event_type IN ('consent.recorded','consent.revoked','packet.exported') AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL AND document_id IS NULL AND identifier_id IS NULL AND review_id IS NULL AND consent_id IS NOT NULL));

CREATE TABLE public.tenant_audit_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 actor_subject text NOT NULL CHECK (length(actor_subject) BETWEEN 1 AND 255),
 event_type text NOT NULL CHECK (event_type IN ('source.registered','source.withdrawn')),
 source_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY (tenant_id, source_id) REFERENCES public.evidence_sources(tenant_id, id)
);
ALTER TABLE public.tenant_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_audit_read ON public.tenant_audit_events FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND actor_subject = nullif(current_setting('app.subject_id', true), '')
);
REVOKE ALL ON public.tenant_audit_events FROM PUBLIC;

CREATE TABLE public.audit_ledger (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 source_event_id uuid NOT NULL UNIQUE,
 source_table text NOT NULL CHECK (source_table IN ('property_audit_events','tenant_audit_events')),
 tenant_id uuid NOT NULL,
 property_id uuid,
 actor_subject text NOT NULL,
 event_type text NOT NULL,
 recorded_at timestamptz NOT NULL,
 delivered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 target_subject text,
 access_expires_at timestamptz,
 claim_id uuid,
 correction_id uuid,
 document_id uuid,
 identifier_id uuid,
 review_id uuid,
 consent_id uuid,
 source_id uuid,
 CHECK (
  (source_table = 'property_audit_events' AND property_id IS NOT NULL AND source_id IS NULL)
  OR (source_table = 'tenant_audit_events' AND property_id IS NULL AND source_id IS NOT NULL))
);
CREATE INDEX audit_ledger_page_idx ON public.audit_ledger(tenant_id, property_id, recorded_at DESC, id DESC);
ALTER TABLE public.audit_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_ledger FORCE ROW LEVEL SECURITY;
CREATE POLICY ledger_private_read ON public.audit_ledger FOR SELECT USING (
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id = audit_ledger.tenant_id
  AND m.subject_id = nullif(current_setting('app.subject_id', true), ''))
 AND (
  property_id IS NULL
  OR EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id = audit_ledger.tenant_id AND p.id = audit_ledger.property_id)
 )
);
REVOKE ALL ON public.audit_ledger FROM PUBLIC;

CREATE FUNCTION public.ledger_row_must_match_outbox()
 RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
 IF NEW.source_table = 'property_audit_events' THEN
  PERFORM 1 FROM public.property_audit_events e
   WHERE e.id = NEW.source_event_id AND e.tenant_id = NEW.tenant_id AND e.property_id = NEW.property_id
    AND e.actor_subject = NEW.actor_subject AND e.event_type = NEW.event_type AND e.created_at = NEW.recorded_at
    AND e.target_subject IS NOT DISTINCT FROM NEW.target_subject
    AND e.access_expires_at IS NOT DISTINCT FROM NEW.access_expires_at
    AND e.claim_id IS NOT DISTINCT FROM NEW.claim_id
    AND e.correction_id IS NOT DISTINCT FROM NEW.correction_id
    AND e.document_id IS NOT DISTINCT FROM NEW.document_id
    AND e.identifier_id IS NOT DISTINCT FROM NEW.identifier_id
    AND e.review_id IS NOT DISTINCT FROM NEW.review_id
    AND e.consent_id IS NOT DISTINCT FROM NEW.consent_id;
 ELSIF NEW.source_table = 'tenant_audit_events' THEN
  PERFORM 1 FROM public.tenant_audit_events e
   WHERE e.id = NEW.source_event_id AND e.tenant_id = NEW.tenant_id AND e.source_id = NEW.source_id
    AND e.actor_subject = NEW.actor_subject AND e.event_type = NEW.event_type AND e.created_at = NEW.recorded_at;
 ELSE
  RAISE EXCEPTION 'Audit ledger is append-only' USING ERRCODE = '42501';
 END IF;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Audit ledger is append-only' USING ERRCODE = '42501';
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.ledger_row_must_match_outbox() FROM PUBLIC;

CREATE TRIGGER audit_ledger_must_match
 BEFORE INSERT ON public.audit_ledger
 FOR EACH ROW EXECUTE FUNCTION public.ledger_row_must_match_outbox();

INSERT INTO public.audit_ledger (
 source_event_id, source_table, tenant_id, property_id, actor_subject, event_type, recorded_at,
 target_subject, access_expires_at, claim_id, correction_id, document_id, identifier_id, review_id, consent_id)
SELECT id, 'property_audit_events', tenant_id, property_id, actor_subject, event_type, created_at,
 target_subject, access_expires_at, claim_id, correction_id, document_id, identifier_id, review_id, consent_id
FROM public.property_audit_events;

CREATE FUNCTION public.copy_property_audit()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
 INSERT INTO public.audit_ledger (
  source_event_id, source_table, tenant_id, property_id, actor_subject, event_type, recorded_at,
  target_subject, access_expires_at, claim_id, correction_id, document_id, identifier_id, review_id, consent_id)
 VALUES (
  NEW.id, 'property_audit_events', NEW.tenant_id, NEW.property_id, NEW.actor_subject, NEW.event_type, NEW.created_at,
  NEW.target_subject, NEW.access_expires_at, NEW.claim_id, NEW.correction_id, NEW.document_id,
  NEW.identifier_id, NEW.review_id, NEW.consent_id);
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.copy_property_audit() FROM PUBLIC;

CREATE TRIGGER property_audit_deliver
 AFTER INSERT ON public.property_audit_events
 FOR EACH ROW EXECUTE FUNCTION public.copy_property_audit();

CREATE FUNCTION public.copy_tenant_audit()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
 INSERT INTO public.audit_ledger (
  source_event_id, source_table, tenant_id, actor_subject, event_type, recorded_at, source_id)
 VALUES (NEW.id, 'tenant_audit_events', NEW.tenant_id, NEW.actor_subject, NEW.event_type, NEW.created_at, NEW.source_id);
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.copy_tenant_audit() FROM PUBLIC;

CREATE TRIGGER tenant_audit_deliver
 AFTER INSERT ON public.tenant_audit_events
 FOR EACH ROW EXECUTE FUNCTION public.copy_tenant_audit();

CREATE FUNCTION public.reject_ledger_rewrite()
 RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
 RAISE EXCEPTION 'Audit ledger is append-only' USING ERRCODE = '42501';
END $$;
REVOKE ALL ON FUNCTION public.reject_ledger_rewrite() FROM PUBLIC;

CREATE TRIGGER audit_ledger_no_update
 BEFORE UPDATE OR DELETE ON public.audit_ledger
 FOR EACH ROW EXECUTE FUNCTION public.reject_ledger_rewrite();
CREATE TRIGGER audit_ledger_no_truncate
 BEFORE TRUNCATE ON public.audit_ledger
 FOR EACH STATEMENT EXECUTE FUNCTION public.reject_ledger_rewrite();

CREATE FUNCTION public.actor_can_edit_property(t uuid, p uuid)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), '');
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL THEN
  RETURN false;
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id = t AND subject_id = actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM public.properties WHERE tenant_id = t AND id = p AND (
  created_by = actor OR EXISTS (
   SELECT 1 FROM public.property_write_grants g WHERE g.tenant_id = t AND g.property_id = p AND g.subject_id = actor
    AND NOT g.revoked AND g.expires_at > clock_timestamp())) FOR SHARE;
 RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION public.actor_can_edit_property(uuid, uuid) FROM PUBLIC;

CREATE FUNCTION public.record_property_identifier(t uuid, p uuid, identifier_scheme text, next_value text, resolution text)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, scheme text, identifier_value text, version integer,
  status text, recorded_by text, recorded_at timestamptz, changed boolean)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
 actor text := nullif(current_setting('app.subject_id', true), '');
 current_id uuid; current_value text; next_version integer; new_id uuid; new_status text;
BEGIN
 next_value := btrim(next_value);
 IF actor IS NULL OR identifier_scheme IS NULL OR identifier_scheme NOT IN ('internal','survey','municipal','khata')
  OR next_value IS NULL OR length(next_value) NOT BETWEEN 1 AND 120
  OR next_value ~ '[[:cntrl:]]'
  OR (resolution IS NOT NULL AND resolution NOT IN ('supersede','conflict')) THEN
  RAISE EXCEPTION 'Invalid identifier' USING ERRCODE = '22023';
 END IF;
 IF NOT public.actor_can_edit_property(t, p) THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/identifier/' || p::text || '/' || identifier_scheme, 0));
 SELECT i.id, i.identifier_value INTO current_id, current_value
  FROM public.property_identifiers i
  WHERE i.tenant_id = t AND i.property_id = p AND i.scheme = identifier_scheme AND i.status = 'current'
  FOR UPDATE;
 IF current_id IS NOT NULL AND current_value = next_value THEN
  RETURN QUERY SELECT i.id, i.tenant_id, i.property_id, i.scheme, i.identifier_value, i.version,
   i.status, i.recorded_by, i.recorded_at, false
   FROM public.property_identifiers i WHERE i.id = current_id;
  RETURN;
 END IF;
 IF current_id IS NULL THEN
  IF resolution IS NOT NULL THEN
   RAISE EXCEPTION 'Invalid identifier' USING ERRCODE = '22023';
  END IF;
  next_version := 1;
  new_status := 'current';
 ELSE
  IF resolution IS NULL THEN
   RAISE EXCEPTION 'Identifier resolution required' USING ERRCODE = '22023';
  END IF;
  SELECT COALESCE(MAX(i.version), 0) + 1 INTO next_version
   FROM public.property_identifiers i WHERE i.tenant_id = t AND i.property_id = p AND i.scheme = identifier_scheme;
  IF resolution = 'supersede' THEN
   UPDATE public.property_identifiers SET status = 'superseded'
    WHERE public.property_identifiers.id = current_id AND status = 'current';
   new_status := 'current';
  ELSE
   new_status := 'conflict';
  END IF;
 END IF;
 INSERT INTO public.property_identifiers (
  tenant_id, property_id, scheme, identifier_value, version, status, recorded_by, related_id)
 VALUES (t, p, identifier_scheme, next_value, next_version, new_status, actor,
  CASE WHEN current_id IS NULL THEN NULL ELSE current_id END)
 RETURNING public.property_identifiers.id INTO new_id;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, identifier_id)
 VALUES (t, p, actor, CASE WHEN new_status = 'conflict' THEN 'identifier.conflict' ELSE 'identifier.recorded' END, new_id);
 RETURN QUERY SELECT i.id, i.tenant_id, i.property_id, i.scheme, i.identifier_value, i.version,
  i.status, i.recorded_by, i.recorded_at, true
  FROM public.property_identifiers i WHERE i.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.record_property_identifier(uuid, uuid, text, text, text) FROM PUBLIC;

CREATE FUNCTION public.register_evidence_source(t uuid, source_name text, source_origin text, source_jurisdiction text)
 RETURNS TABLE (
  id uuid, tenant_id uuid, name text, origin text, jurisdiction text, rights_status text,
  created_by text, created_at timestamptz, withdrawn_at timestamptz, withdrawal_reason text)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), ''); new_id uuid;
BEGIN
 source_name := btrim(source_name);
 source_jurisdiction := btrim(source_jurisdiction);
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL
  OR source_name IS NULL OR length(source_name) NOT BETWEEN 1 AND 200
  OR source_origin IS NULL OR source_origin NOT IN ('user_supplied','professional','published_notice')
  OR source_jurisdiction IS NULL OR length(source_jurisdiction) NOT BETWEEN 1 AND 100 THEN
  RAISE EXCEPTION 'Invalid source' USING ERRCODE = '22023';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id = t AND subject_id = actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 INSERT INTO public.evidence_sources (tenant_id, name, origin, jurisdiction, created_by)
 VALUES (t, source_name, source_origin, source_jurisdiction, actor)
 RETURNING public.evidence_sources.id INTO new_id;
 INSERT INTO public.tenant_audit_events (tenant_id, actor_subject, event_type, source_id)
 VALUES (t, actor, 'source.registered', new_id);
 RETURN QUERY SELECT s.id, s.tenant_id, s.name, s.origin, s.jurisdiction, s.rights_status,
  s.created_by, s.created_at, s.withdrawn_at, s.withdrawal_reason
  FROM public.evidence_sources s WHERE s.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.register_evidence_source(uuid, text, text, text) FROM PUBLIC;

CREATE FUNCTION public.withdraw_evidence_source(t uuid, source uuid, reason text)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), '');
BEGIN
 reason := btrim(reason);
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL
  OR reason IS NULL OR length(reason) NOT BETWEEN 1 AND 500 THEN
  RAISE EXCEPTION 'Invalid source' USING ERRCODE = '22023';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id = t AND subject_id = actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 PERFORM 1 FROM public.evidence_sources WHERE tenant_id = t AND id = source FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 UPDATE public.evidence_sources SET withdrawn_at = clock_timestamp(), withdrawal_reason = reason
  WHERE tenant_id = t AND id = source AND withdrawn_at IS NULL;
 IF NOT FOUND THEN RETURN false; END IF;
 INSERT INTO public.tenant_audit_events (tenant_id, actor_subject, event_type, source_id)
 VALUES (t, actor, 'source.withdrawn', source);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.withdraw_evidence_source(uuid, uuid, text) FROM PUBLIC;

CREATE FUNCTION public.record_professional_review(t uuid, p uuid, review_disposition text, review_statement text, cited_source uuid)
 RETURNS TABLE (
  id uuid, tenant_id uuid, property_id uuid, reviewer_subject text, disposition text,
  statement text, source_id uuid, recorded_at timestamptz)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), ''); new_id uuid;
BEGIN
 review_statement := btrim(review_statement);
 IF actor IS NULL OR review_disposition IS NULL OR review_disposition NOT IN ('recorded','abstained')
  OR review_statement IS NULL OR length(review_statement) NOT BETWEEN 1 AND 2000 THEN
  RAISE EXCEPTION 'Invalid review' USING ERRCODE = '22023';
 END IF;
 IF NOT public.actor_can_edit_property(t, p) THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 IF cited_source IS NOT NULL THEN
  PERFORM 1 FROM public.evidence_sources WHERE tenant_id = t AND id = cited_source AND withdrawn_at IS NULL FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Source is withdrawn' USING ERRCODE = '22023'; END IF;
 END IF;
 INSERT INTO public.professional_reviews (
  tenant_id, property_id, reviewer_subject, disposition, statement, source_id)
 VALUES (t, p, actor, review_disposition, review_statement, cited_source)
 RETURNING public.professional_reviews.id INTO new_id;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, review_id)
 VALUES (t, p, actor, 'review.recorded', new_id);
 RETURN QUERY SELECT r.id, r.tenant_id, r.property_id, r.reviewer_subject, r.disposition,
  r.statement, r.source_id, r.recorded_at
  FROM public.professional_reviews r WHERE r.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.record_professional_review(uuid, uuid, text, text, uuid) FROM PUBLIC;

CREATE FUNCTION public.record_property_consent(t uuid, p uuid, consent_purpose text)
 RETURNS TABLE (id uuid, tenant_id uuid, property_id uuid, subject_id text, purpose text, granted_at timestamptz, revoked_at timestamptz, changed boolean)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), ''); existing uuid; new_id uuid;
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL
  OR consent_purpose IS DISTINCT FROM 'passport_export' THEN
  RAISE EXCEPTION 'Invalid request' USING ERRCODE = '22023';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id = t AND subject_id = actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 PERFORM 1 FROM public.properties WHERE tenant_id = t AND id = p AND created_by = actor FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/consent/' || p::text, 0));
 SELECT c.id INTO existing FROM public.property_consents c
  WHERE c.tenant_id = t AND c.property_id = p AND c.purpose = consent_purpose AND c.revoked_at IS NULL;
 IF existing IS NOT NULL THEN
  RETURN QUERY SELECT c.id, c.tenant_id, c.property_id, c.subject_id, c.purpose, c.granted_at, c.revoked_at, false
   FROM public.property_consents c WHERE c.id = existing;
  RETURN;
 END IF;
 INSERT INTO public.property_consents (tenant_id, property_id, subject_id, purpose)
 VALUES (t, p, actor, consent_purpose)
 RETURNING public.property_consents.id INTO new_id;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, consent_id)
 VALUES (t, p, actor, 'consent.recorded', new_id);
 RETURN QUERY SELECT c.id, c.tenant_id, c.property_id, c.subject_id, c.purpose, c.granted_at, c.revoked_at, true
  FROM public.property_consents c WHERE c.id = new_id;
END $$;
REVOKE ALL ON FUNCTION public.record_property_consent(uuid, uuid, text) FROM PUBLIC;

CREATE FUNCTION public.revoke_property_consent(t uuid, p uuid, consent_purpose text)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), ''); consent uuid;
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL
  OR consent_purpose IS DISTINCT FROM 'passport_export' THEN
  RAISE EXCEPTION 'Invalid request' USING ERRCODE = '22023';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id = t AND subject_id = actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 PERFORM 1 FROM public.properties WHERE tenant_id = t AND id = p AND created_by = actor FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/consent/' || p::text, 0));
 SELECT c.id INTO consent FROM public.property_consents c
  WHERE c.tenant_id = t AND c.property_id = p AND c.purpose = consent_purpose AND c.revoked_at IS NULL
  FOR UPDATE;
 IF consent IS NULL THEN RETURN false; END IF;
 UPDATE public.property_consents SET revoked_at = clock_timestamp()
  WHERE public.property_consents.id = consent AND revoked_at IS NULL;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, consent_id)
 VALUES (t, p, actor, 'consent.revoked', consent);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.revoke_property_consent(uuid, uuid, text) FROM PUBLIC;

CREATE FUNCTION public.authorize_property_export(t uuid, p uuid)
 RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE actor text := nullif(current_setting('app.subject_id', true), ''); consent uuid;
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid OR actor IS NULL THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id = t AND subject_id = actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 PERFORM 1 FROM public.properties WHERE tenant_id = t AND id = p AND created_by = actor FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/consent/' || p::text, 0));
 SELECT c.id INTO consent FROM public.property_consents c
  WHERE c.tenant_id = t AND c.property_id = p AND c.purpose = 'passport_export' AND c.revoked_at IS NULL
  FOR SHARE;
 IF consent IS NULL THEN
  RAISE EXCEPTION 'Export consent required' USING ERRCODE = '22023';
 END IF;
 INSERT INTO public.property_audit_events (tenant_id, property_id, actor_subject, event_type, consent_id)
 VALUES (t, p, actor, 'packet.exported', consent);
 RETURN consent;
END $$;
REVOKE ALL ON FUNCTION public.authorize_property_export(uuid, uuid) FROM PUBLIC;
