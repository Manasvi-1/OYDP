-- Run using a migration owner; the application role must not own tables or have BYPASSRLS.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS properties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    label text NOT NULL CHECK (length(label) BETWEEN 1 AND 200),
    jurisdiction text NOT NULL CHECK (length(jurisdiction) BETWEEN 1 AND 100),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS properties_tenant_idx ON properties (tenant_id, created_at);
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS property_tenant_policy ON properties;
CREATE POLICY property_tenant_policy ON properties
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
-- Privileges must be granted to a separately provisioned non-owner runtime role.
