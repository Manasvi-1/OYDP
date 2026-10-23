BEGIN;
ALTER TABLE oydp.audit_outbox DROP CONSTRAINT audit_outbox_event_type_check;
ALTER TABLE oydp.audit_outbox ADD CONSTRAINT audit_outbox_event_type_check
 CHECK(event_type IN ('property.created','claim.recorded','access.changed','access.revoked'));
ALTER TABLE oydp.audit_outbox ADD COLUMN target_subject_id uuid;
ALTER TABLE oydp.audit_outbox ADD COLUMN granted_actions text[];
ALTER TABLE oydp.audit_outbox ADD COLUMN access_expires_at timestamptz;
ALTER TABLE oydp.audit_outbox ADD CONSTRAINT audit_access_shape CHECK (
 (event_type IN ('property.created','claim.recorded') AND target_subject_id IS NULL
   AND granted_actions IS NULL AND access_expires_at IS NULL)
 OR (event_type='access.changed' AND target_subject_id IS NOT NULL
   AND granted_actions IS NOT NULL AND cardinality(granted_actions)>0 AND access_expires_at IS NOT NULL)
 OR (event_type='access.revoked' AND target_subject_id IS NOT NULL
   AND granted_actions IS NOT NULL AND cardinality(granted_actions)=0 AND access_expires_at IS NULL));

-- Ordinary application SQL may bootstrap only the creator's own grants.
-- Sharing uses the narrowly scoped, audited function below.
CREATE POLICY grants_creator_insert ON oydp.grants AS RESTRICTIVE FOR INSERT
 WITH CHECK(subject_id=oydp.subject_id() AND EXISTS (
   SELECT 1 FROM oydp.properties p WHERE p.tenant_id=grants.tenant_id
   AND p.id=grants.property_id AND p.created_by=oydp.subject_id()));

CREATE FUNCTION oydp.set_property_access(
 t uuid, p uuid, recipient uuid, permissions text[], expiry timestamptz
) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE actor uuid := oydp.subject_id(); changed boolean; controller_expiry timestamptz;
BEGIN
 IF t IS DISTINCT FROM oydp.tenant_id() OR actor IS NULL OR recipient IS NULL
    OR recipient=actor THEN
   RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002';
 END IF;
 IF permissions IS NULL OR cardinality(permissions)>2
    OR array_position(permissions,NULL) IS NOT NULL
    OR NOT permissions <@ ARRAY['property:read','property:write']::text[]
    OR (cardinality(permissions)>0 AND NOT 'property:read'=ANY(permissions))
    OR (cardinality(permissions)>0 AND (expiry IS NULL OR expiry<=clock_timestamp()
        OR expiry>clock_timestamp()+interval '30 days'))
    OR (cardinality(permissions)=0 AND expiry IS NOT NULL) THEN
   RAISE EXCEPTION 'Invalid access request' USING ERRCODE='22023';
 END IF;
 PERFORM 1 FROM oydp.memberships WHERE tenant_id=t AND subject_id=actor AND active FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 -- Serialize changes per property without widening runtime table UPDATE rights.
 PERFORM pg_advisory_xact_lock(hashtextextended(t::text || '/' || p::text,0));
 PERFORM 1 FROM oydp.properties WHERE tenant_id=t AND id=p AND created_by=actor;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 SELECT expires_at INTO controller_expiry FROM oydp.grants WHERE tenant_id=t AND property_id=p AND subject_id=actor
   AND action='property:write' AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 IF expiry>controller_expiry THEN
   RAISE EXCEPTION 'Invalid access request' USING ERRCODE='22023';
 END IF;
 IF cardinality(permissions)>0 THEN
   PERFORM 1 FROM oydp.memberships WHERE tenant_id=t AND subject_id=recipient AND active FOR SHARE;
   IF NOT FOUND THEN RAISE EXCEPTION 'Resource unavailable' USING ERRCODE='P0002'; END IF;
 END IF;
 -- Do nothing (and do not duplicate audit events) for an identical request.
 SELECT EXISTS(SELECT 1 FROM oydp.grants WHERE tenant_id=t AND property_id=p
   AND subject_id=recipient AND NOT revoked AND
   (NOT action=ANY(permissions) OR expires_at IS DISTINCT FROM expiry)) OR
   EXISTS(SELECT 1 FROM unnest(permissions) requested WHERE NOT EXISTS (
     SELECT 1 FROM oydp.grants WHERE tenant_id=t AND property_id=p AND subject_id=recipient
     AND action=requested AND NOT revoked AND expires_at=expiry)) INTO changed;
 IF NOT changed THEN RETURN false; END IF;
 UPDATE oydp.grants SET revoked=true WHERE tenant_id=t AND property_id=p
   AND subject_id=recipient AND NOT revoked AND NOT action=ANY(permissions);
 INSERT INTO oydp.grants(tenant_id,property_id,subject_id,action,expires_at)
   SELECT t,p,recipient,action,expiry FROM (SELECT DISTINCT unnest(permissions) AS action) q
 ON CONFLICT(tenant_id,property_id,subject_id,action)
 DO UPDATE SET revoked=false,expires_at=EXCLUDED.expires_at;
 INSERT INTO oydp.audit_outbox(tenant_id,id,property_id,actor_id,event_type,
   target_subject_id,granted_actions,access_expires_at)
 VALUES(t,gen_random_uuid(),p,actor,
   CASE WHEN cardinality(permissions)=0 THEN 'access.revoked' ELSE 'access.changed' END,
   recipient,ARRAY(SELECT DISTINCT unnest(permissions) ORDER BY 1),expiry);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION oydp.set_property_access(uuid,uuid,uuid,text[],timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION oydp.set_property_access(uuid,uuid,uuid,text[],timestamptz) TO oydp_runtime;
COMMIT;
