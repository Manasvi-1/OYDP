-- Stable identifiers for keyset pages of write grants. Existing grant keys stay in place.
ALTER TABLE public.property_write_grants
  ADD COLUMN id uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE public.property_write_grants
  ADD CONSTRAINT property_write_grants_id_key UNIQUE (id);
CREATE INDEX write_grants_page_idx
  ON public.property_write_grants(tenant_id, property_id, expires_at DESC, id DESC);

-- A current write grant can see that one property. Direct updates stay creator-only.
-- This reads only grant rows, as the function owner, so property policies do not recurse
-- and INSERT ... RETURNING can still see the new row.
CREATE FUNCTION public.actor_has_live_write_grant(t uuid, p uuid)
 RETURNS boolean LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT EXISTS (
  SELECT 1 FROM public.property_write_grants w
  WHERE w.tenant_id=t AND w.property_id=p
  AND w.subject_id=nullif(current_setting('app.subject_id',true),'')
  AND NOT w.revoked AND w.expires_at>clock_timestamp()
 );
$$;
REVOKE ALL ON FUNCTION public.actor_has_live_write_grant(uuid,uuid) FROM PUBLIC;

DROP POLICY property_private_read ON public.properties;
CREATE POLICY property_private_read ON public.properties FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS (SELECT 1 FROM public.tenant_memberships m WHERE m.tenant_id=properties.tenant_id
   AND m.subject_id=nullif(current_setting('app.subject_id',true),''))
 AND (created_by=nullif(current_setting('app.subject_id',true),'') OR EXISTS (
   SELECT 1 FROM public.property_read_grants g WHERE g.tenant_id=properties.tenant_id
   AND g.property_id=properties.id AND NOT g.revoked AND g.expires_at>clock_timestamp())
   OR public.actor_has_live_write_grant(properties.tenant_id, properties.id))
);
