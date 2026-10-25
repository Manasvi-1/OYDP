-- Move canonical property records from tenant-wide reads to creator/read-grant access.
-- Only unambiguous, existing creation audit evidence may attribute an old record.
ALTER TABLE public.properties ADD COLUMN created_by text
    CHECK (created_by IS NULL OR length(created_by) BETWEEN 1 AND 255);
WITH attribution AS (
 SELECT tenant_id, property_id, min(actor_subject) AS actor
 FROM public.property_audit_events WHERE event_type='property.created'
 GROUP BY tenant_id, property_id HAVING count(DISTINCT actor_subject)=1
)
UPDATE public.properties p SET created_by=a.actor FROM attribution a
 WHERE p.tenant_id=a.tenant_id AND p.id=a.property_id;
ALTER TABLE public.properties ALTER COLUMN created_by
 SET DEFAULT nullif(current_setting('app.subject_id',true),'');

CREATE TABLE public.property_read_grants (
 tenant_id uuid NOT NULL, property_id uuid NOT NULL, subject_id text NOT NULL,
 expires_at timestamptz NOT NULL, revoked boolean NOT NULL DEFAULT false,
 PRIMARY KEY(tenant_id,property_id,subject_id),
 FOREIGN KEY(tenant_id,property_id) REFERENCES public.properties(tenant_id,id),
 FOREIGN KEY(tenant_id,subject_id) REFERENCES public.tenant_memberships(tenant_id,subject_id) ON DELETE CASCADE
);
ALTER TABLE public.property_read_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.property_read_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY read_own_grants ON public.property_read_grants FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND subject_id=nullif(current_setting('app.subject_id',true),'')
);
-- FOR SHARE requires UPDATE privileges; WITH CHECK(false) forbids mutation.
CREATE POLICY lock_own_grants ON public.property_read_grants FOR UPDATE USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND subject_id=nullif(current_setting('app.subject_id',true),'')
) WITH CHECK(false);
CREATE POLICY lock_own_membership ON public.tenant_memberships FOR UPDATE USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND subject_id=nullif(current_setting('app.subject_id',true),'')
) WITH CHECK(false);

DROP POLICY property_tenant_policy ON public.properties;
CREATE POLICY property_private_read ON public.properties FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=properties.tenant_id
   AND m.subject_id=nullif(current_setting('app.subject_id',true),''))
 AND (created_by=nullif(current_setting('app.subject_id',true),'') OR EXISTS (
   SELECT 1 FROM public.property_read_grants g WHERE g.tenant_id=properties.tenant_id
   AND g.property_id=properties.id AND NOT g.revoked AND g.expires_at>clock_timestamp()))
);
CREATE POLICY property_private_create ON public.properties FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND created_by=nullif(current_setting('app.subject_id',true),'')
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=properties.tenant_id
   AND m.subject_id=properties.created_by AND m.role IN ('owner','editor'))
);
CREATE POLICY property_no_update ON public.properties FOR UPDATE USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND created_by=nullif(current_setting('app.subject_id',true),'')
) WITH CHECK(false);
-- No DELETE policy: physical record deletion is not an implemented capability.

DROP POLICY assertion_tenant_policy ON public.evidence_assertions;
CREATE POLICY assertion_private_read ON public.evidence_assertions FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=evidence_assertions.tenant_id
 AND p.id=evidence_assertions.property_id)
);
CREATE POLICY assertion_creator_insert ON public.evidence_assertions FOR INSERT WITH CHECK (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=evidence_assertions.tenant_id
 AND p.id=evidence_assertions.property_id AND p.created_by=nullif(current_setting('app.subject_id',true),''))
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=evidence_assertions.tenant_id
 AND m.subject_id=nullif(current_setting('app.subject_id',true),'') AND m.role IN ('owner','editor'))
);
DROP POLICY audit_read ON public.property_audit_events;
CREATE POLICY audit_private_read ON public.property_audit_events FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=property_audit_events.tenant_id
 AND p.id=property_audit_events.property_id)
);
ALTER TABLE public.property_audit_events DROP CONSTRAINT property_audit_events_event_type_check;
ALTER TABLE public.property_audit_events ADD CONSTRAINT property_audit_events_event_type_check
 CHECK(event_type IN ('property.created','access.granted','access.revoked'));
ALTER TABLE public.property_audit_events ADD COLUMN target_subject text;
ALTER TABLE public.property_audit_events ADD COLUMN access_expires_at timestamptz;
ALTER TABLE public.property_audit_events ADD CONSTRAINT access_audit_shape CHECK (
 (event_type='property.created' AND target_subject IS NULL AND access_expires_at IS NULL)
 OR (event_type='access.granted' AND target_subject IS NOT NULL AND access_expires_at IS NOT NULL)
 OR (event_type='access.revoked' AND target_subject IS NOT NULL AND access_expires_at IS NULL));

CREATE FUNCTION public.set_property_read_access(t uuid, p uuid, recipient text, expiry timestamptz)
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
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/' || p::text,0));
 PERFORM 1 FROM public.properties WHERE tenant_id=t AND id=p AND created_by=actor FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 IF expiry IS NOT NULL THEN
  PERFORM 1 FROM public.tenant_memberships WHERE tenant_id=t AND subject_id=recipient FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
  SELECT NOT EXISTS(SELECT 1 FROM public.property_read_grants WHERE tenant_id=t AND property_id=p
    AND subject_id=recipient AND NOT revoked AND expires_at=expiry) INTO changed;
  IF NOT changed THEN RETURN false; END IF;
  INSERT INTO public.property_read_grants(tenant_id,property_id,subject_id,expires_at) VALUES(t,p,recipient,expiry)
   ON CONFLICT(tenant_id,property_id,subject_id) DO UPDATE SET revoked=false,expires_at=EXCLUDED.expires_at;
 ELSE
  UPDATE public.property_read_grants SET revoked=true WHERE tenant_id=t AND property_id=p AND subject_id=recipient AND NOT revoked;
  changed := FOUND;
  IF NOT changed THEN RETURN false; END IF;
 END IF;
 INSERT INTO public.property_audit_events(tenant_id,property_id,actor_subject,event_type,target_subject,access_expires_at)
 VALUES(t,p,actor,CASE WHEN expiry IS NULL THEN 'access.revoked' ELSE 'access.granted' END,recipient,expiry);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.set_property_read_access(uuid,uuid,text,timestamptz) FROM PUBLIC;
-- Runtime grants are applied explicitly by scripts/migrate.py --provision-runtime.
