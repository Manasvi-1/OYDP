BEGIN;
CREATE SCHEMA oydp;
CREATE TABLE oydp.memberships (
 tenant_id uuid NOT NULL, subject_id uuid NOT NULL, active boolean NOT NULL DEFAULT true,
 PRIMARY KEY(tenant_id, subject_id)
);
CREATE TABLE oydp.properties (
 tenant_id uuid NOT NULL, id uuid NOT NULL, created_by uuid NOT NULL,
 name text NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 200),
 jurisdiction text NOT NULL CHECK(length(btrim(jurisdiction)) BETWEEN 1 AND 200),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,created_by) REFERENCES oydp.memberships(tenant_id,subject_id)
);
CREATE TABLE oydp.grants (
 tenant_id uuid NOT NULL, property_id uuid NOT NULL, subject_id uuid NOT NULL,
 action text NOT NULL CHECK(action IN ('property:read','property:write')),
 expires_at timestamptz NOT NULL, revoked boolean NOT NULL DEFAULT false,
 PRIMARY KEY(tenant_id,property_id,subject_id,action),
 FOREIGN KEY(tenant_id,property_id) REFERENCES oydp.properties(tenant_id,id),
 FOREIGN KEY(tenant_id,subject_id) REFERENCES oydp.memberships(tenant_id,subject_id)
);
CREATE TABLE oydp.claims (
 tenant_id uuid NOT NULL, property_id uuid NOT NULL, id uuid NOT NULL, created_by uuid NOT NULL,
 statement text NOT NULL CHECK(length(btrim(statement)) BETWEEN 1 AND 10000),
 kind text NOT NULL DEFAULT 'user_claim' CHECK(kind='user_claim'),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,property_id,id),
 FOREIGN KEY(tenant_id,property_id) REFERENCES oydp.properties(tenant_id,id),
 FOREIGN KEY(tenant_id,created_by) REFERENCES oydp.memberships(tenant_id,subject_id)
);
CREATE TABLE oydp.audit_outbox (
 tenant_id uuid NOT NULL, id uuid NOT NULL, property_id uuid NOT NULL, actor_id uuid NOT NULL,
 event_type text NOT NULL CHECK(event_type IN ('property.created','claim.recorded')),
 occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,property_id) REFERENCES oydp.properties(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES oydp.memberships(tenant_id,subject_id)
);
CREATE FUNCTION oydp.tenant_id() RETURNS uuid LANGUAGE sql STABLE AS
 $$ SELECT nullif(current_setting('oydp.tenant_id', true),'')::uuid $$;
CREATE FUNCTION oydp.subject_id() RETURNS uuid LANGUAGE sql STABLE AS
 $$ SELECT nullif(current_setting('oydp.subject_id', true),'')::uuid $$;
ALTER TABLE oydp.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE oydp.memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_context ON oydp.memberships FOR SELECT
 USING(tenant_id=oydp.tenant_id() AND subject_id=oydp.subject_id());
-- Row locking also evaluates UPDATE visibility. Permit locking, never mutation.
CREATE POLICY membership_lock ON oydp.memberships FOR UPDATE
 USING(tenant_id=oydp.tenant_id() AND subject_id=oydp.subject_id()) WITH CHECK(false);
CREATE FUNCTION oydp.active_member(t uuid) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT t=oydp.tenant_id() AND EXISTS(
 SELECT 1 FROM oydp.memberships m WHERE m.tenant_id=t AND m.subject_id=oydp.subject_id() AND m.active)
$$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['properties','grants','claims','audit_outbox'] LOOP
 EXECUTE format('ALTER TABLE oydp.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE oydp.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('CREATE POLICY tenant_isolation ON oydp.%I USING (oydp.active_member(tenant_id)) WITH CHECK (oydp.active_member(tenant_id))',t);
 END LOOP;
END $$;
CREATE POLICY grants_no_mutation ON oydp.grants AS RESTRICTIVE FOR UPDATE
 USING(true) WITH CHECK(false);
CREATE INDEX properties_recent ON oydp.properties(tenant_id,created_at DESC,id);
CREATE INDEX claims_property ON oydp.claims(tenant_id,property_id,recorded_at,id);
-- A deployment administrator creates oydp_runtime as a non-owner, non-BYPASSRLS role.
-- Only these capabilities are granted. Membership provisioning/revocation is a separate trusted operation.
GRANT USAGE ON SCHEMA oydp TO oydp_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA oydp TO oydp_runtime;
GRANT INSERT ON oydp.properties,oydp.grants,oydp.claims,oydp.audit_outbox TO oydp_runtime;
-- FOR SHARE requires UPDATE privilege; column-scoped privilege avoids editing membership state.
GRANT UPDATE(subject_id) ON oydp.memberships TO oydp_runtime;
GRANT UPDATE(subject_id) ON oydp.grants TO oydp_runtime;
COMMIT;
