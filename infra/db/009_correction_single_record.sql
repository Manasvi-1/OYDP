-- A correction rewrites one property label or jurisdiction and appends history.
-- It does not delete, reassign, or merge a conflicting property record.
CREATE OR REPLACE FUNCTION public.correct_property(t uuid, p uuid, new_label text, new_jurisdiction text)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE actor text := nullif(current_setting('app.subject_id',true),'');
 current_label text; current_jurisdiction text; creator text; correction uuid; kept_creator text;
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
 -- RETURNING INTO STRICT updates this id only. Zero rows or more than one row aborts.
 -- A second property with the same label and jurisdiction is left untouched.
 UPDATE public.properties
  SET label=new_label, jurisdiction=new_jurisdiction
  WHERE tenant_id=t AND id=p
  RETURNING created_by INTO STRICT kept_creator;
 IF kept_creator IS DISTINCT FROM creator THEN
  RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002';
 END IF;
 INSERT INTO public.property_corrections(tenant_id,property_id,actor_subject,previous_label,previous_jurisdiction,label,jurisdiction)
 VALUES(t,p,actor,current_label,current_jurisdiction,new_label,new_jurisdiction) RETURNING id INTO correction;
 INSERT INTO public.property_audit_events(tenant_id,property_id,actor_subject,event_type,correction_id)
 VALUES(t,p,actor,'property.corrected',correction);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.correct_property(uuid,uuid,text,text) FROM PUBLIC;
