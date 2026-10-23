-- Refuse to erase access audit history. Use a forward migration once sharing has been used.
BEGIN;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM oydp.audit_outbox WHERE event_type IN ('access.changed','access.revoked')) THEN
   RAISE EXCEPTION 'Access audit history exists; use a forward migration';
 END IF;
END $$;
DROP FUNCTION oydp.set_property_access(uuid,uuid,uuid,text[],timestamptz);
DROP POLICY grants_creator_insert ON oydp.grants;
ALTER TABLE oydp.audit_outbox DROP CONSTRAINT audit_access_shape;
ALTER TABLE oydp.audit_outbox DROP COLUMN target_subject_id;
ALTER TABLE oydp.audit_outbox DROP COLUMN granted_actions;
ALTER TABLE oydp.audit_outbox DROP COLUMN access_expires_at;
ALTER TABLE oydp.audit_outbox DROP CONSTRAINT audit_outbox_event_type_check;
ALTER TABLE oydp.audit_outbox ADD CONSTRAINT audit_outbox_event_type_check
 CHECK(event_type IN ('property.created','claim.recorded'));
COMMIT;
