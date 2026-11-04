-- Owner-delegated writers and append-only property corrections.
-- The runtime role cannot update property rows or insert these grants.
CREATE TABLE public.property_write_grants (
 tenant_id uuid NOT NULL, property_id uuid NOT NULL, subject_id text NOT NULL,
 expires_at timestamptz NOT NULL, revoked boolean NOT NULL DEFAULT false,
 PRIMARY KEY(tenant_id,property_id,subject_id),
 FOREIGN KEY(tenant_id,property_id) REFERENCES public.properties(tenant_id,id),
 FOREIGN KEY(tenant_id,subject_id) REFERENCES public.tenant_memberships(tenant_id,subject_id) ON DELETE CASCADE
);
ALTER TABLE public.property_write_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_write_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY read_write_grants ON public.property_write_grants FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND (subject_id=nullif(current_setting('app.subject_id',true),'') OR EXISTS (
   SELECT 1 FROM public.properties p WHERE p.tenant_id=property_write_grants.tenant_id
   AND p.id=property_write_grants.property_id
   AND p.created_by=nullif(current_setting('app.subject_id',true),'')))
);
CREATE POLICY lock_write_grants ON public.property_write_grants FOR UPDATE USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND (subject_id=nullif(current_setting('app.subject_id',true),'') OR EXISTS (
   SELECT 1 FROM public.properties p WHERE p.tenant_id=property_write_grants.tenant_id
   AND p.id=property_write_grants.property_id
   AND p.created_by=nullif(current_setting('app.subject_id',true),'')))
) WITH CHECK(false);

CREATE TABLE public.property_corrections (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 actor_subject text NOT NULL CHECK(length(actor_subject) BETWEEN 1 AND 255),
 previous_label text NOT NULL CHECK(length(previous_label) BETWEEN 1 AND 200),
 previous_jurisdiction text NOT NULL CHECK(length(previous_jurisdiction) BETWEEN 1 AND 100),
 label text NOT NULL CHECK(length(label) BETWEEN 1 AND 200),
 jurisdiction text NOT NULL CHECK(length(jurisdiction) BETWEEN 1 AND 100),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,property_id,id),
 FOREIGN KEY(tenant_id,property_id) REFERENCES public.properties(tenant_id,id)
);
CREATE INDEX corrections_page_idx ON public.property_corrections(tenant_id,property_id,recorded_at DESC,id DESC);
ALTER TABLE public.property_corrections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_corrections FORCE ROW LEVEL SECURITY;
CREATE POLICY correction_private_read ON public.property_corrections FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS(SELECT 1 FROM public.properties p WHERE p.tenant_id=property_corrections.tenant_id
  AND p.id=property_corrections.property_id)
);

DROP POLICY claim_creator_append ON public.property_claims;
CREATE POLICY claim_writer_append ON public.property_claims FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND created_by=nullif(current_setting('app.subject_id',true),'')
 AND EXISTS(SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=property_claims.tenant_id
  AND m.subject_id=property_claims.created_by AND m.role IN ('owner','editor'))
 AND EXISTS(SELECT 1 FROM public.properties p WHERE p.tenant_id=property_claims.tenant_id
  AND p.id=property_claims.property_id AND (
   p.created_by=property_claims.created_by OR EXISTS(
    SELECT 1 FROM public.property_write_grants g WHERE g.tenant_id=p.tenant_id AND g.property_id=p.id
    AND g.subject_id=property_claims.created_by AND NOT g.revoked AND g.expires_at>clock_timestamp())))
);

ALTER TABLE public.property_audit_events ADD COLUMN correction_id uuid;
ALTER TABLE public.property_audit_events ADD CONSTRAINT audit_correction_tenant_fk
 FOREIGN KEY(tenant_id,property_id,correction_id) REFERENCES public.property_corrections(tenant_id,property_id,id);
ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK(event_type IN ('property.created','access.granted','access.revoked','claim.recorded','property.corrected','write.granted','write.revoked'));
ALTER TABLE public.property_audit_events DROP CONSTRAINT access_audit_shape;
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type='property.created' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL)
 OR (event_type='access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL AND correction_id IS NULL)
 OR (event_type='access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL)
 OR (event_type='claim.recorded' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NOT NULL AND correction_id IS NULL)
 OR (event_type='property.corrected' AND target_subject IS NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NOT NULL)
 OR (event_type='write.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL AND claim_id IS NULL AND correction_id IS NULL)
 OR (event_type='write.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL AND claim_id IS NULL AND correction_id IS NULL));

CREATE FUNCTION public.set_property_write_access(t uuid, p uuid, recipient text, expiry timestamptz)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id',true),''); changed boolean;
BEGIN
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id',true),'')::uuid
 OR actor IS NULL OR recipient IS NULL OR length(recipient) NOT BETWEEN 1 AND 255
 OR btrim(recipient)='' OR recipient=actor THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002';
 END IF;
 IF expiry IS NOT NULL AND (expiry<=clock_timestamp() OR expiry>clock_timestamp()+interval '30 days') THEN
  RAISE EXCEPTION 'Invalid access expiry' USING ERRCODE='22023';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id=t AND subject_id=actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/write/' || p::text,0));
 PERFORM 1 FROM public.properties WHERE tenant_id=t AND id=p AND created_by=actor FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 IF expiry IS NOT NULL THEN
  PERFORM 1 FROM public.tenant_memberships WHERE tenant_id=t AND subject_id=recipient AND role IN ('owner','editor') FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
  SELECT NOT EXISTS(SELECT 1 FROM public.property_write_grants WHERE tenant_id=t AND property_id=p
    AND subject_id=recipient AND NOT revoked AND expires_at=expiry) INTO changed;
  IF NOT changed THEN RETURN false; END IF;
  INSERT INTO public.property_write_grants(tenant_id,property_id,subject_id,expires_at) VALUES(t,p,recipient,expiry)
   ON CONFLICT(tenant_id,property_id,subject_id) DO UPDATE SET revoked=false,expires_at=EXCLUDED.expires_at;
 ELSE
  UPDATE public.property_write_grants SET revoked=true WHERE tenant_id=t AND property_id=p AND subject_id=recipient AND NOT revoked;
  changed := FOUND;
  IF NOT changed THEN RETURN false; END IF;
 END IF;
 INSERT INTO public.property_audit_events(tenant_id,property_id,actor_subject,event_type,target_subject,access_expires_at)
 VALUES(t,p,actor,CASE WHEN expiry IS NULL THEN 'write.revoked' ELSE 'write.granted' END,recipient,expiry);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.set_property_write_access(uuid,uuid,text,timestamptz) FROM PUBLIC;

CREATE FUNCTION public.correct_property(t uuid, p uuid, new_label text, new_jurisdiction text)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id',true),'');
 current_label text; current_jurisdiction text; creator text; correction uuid;
BEGIN
 new_label := btrim(new_label); new_jurisdiction := btrim(new_jurisdiction);
 IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id',true),'')::uuid OR actor IS NULL
 OR new_label IS NULL OR new_jurisdiction IS NULL
 OR length(new_label) NOT BETWEEN 1 AND 200 OR length(new_jurisdiction) NOT BETWEEN 1 AND 100 THEN
  RAISE EXCEPTION 'Invalid property correction' USING ERRCODE='22023';
 END IF;
 PERFORM 1 FROM public.tenant_memberships WHERE tenant_id=t AND subject_id=actor AND role IN ('owner','editor') FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/write/' || p::text,0));
 SELECT label,jurisdiction,created_by INTO current_label,current_jurisdiction,creator
  FROM public.properties WHERE tenant_id=t AND id=p FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 IF creator IS DISTINCT FROM actor THEN
  PERFORM 1 FROM public.property_write_grants WHERE tenant_id=t AND property_id=p AND subject_id=actor
   AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 END IF;
 IF current_label=new_label AND current_jurisdiction=new_jurisdiction THEN RETURN false; END IF;
 UPDATE public.properties SET label=new_label,jurisdiction=new_jurisdiction WHERE tenant_id=t AND id=p;
 INSERT INTO public.property_corrections(tenant_id,property_id,actor_subject,previous_label,previous_jurisdiction,label,jurisdiction)
 VALUES(t,p,actor,current_label,current_jurisdiction,new_label,new_jurisdiction) RETURNING id INTO correction;
 INSERT INTO public.property_audit_events(tenant_id,property_id,actor_subject,event_type,correction_id)
 VALUES(t,p,actor,'property.corrected',correction);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.correct_property(uuid,uuid,text,text) FROM PUBLIC;
