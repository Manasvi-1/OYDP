CREATE TABLE IF NOT EXISTS tenant_memberships (
    tenant_id uuid NOT NULL,
    subject_id text NOT NULL CHECK (length(subject_id) BETWEEN 1 AND 255),
    role text NOT NULL CHECK (role IN ('owner','editor','viewer')),
    PRIMARY KEY (tenant_id, subject_id)
);
ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_memberships FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS membership_tenant_policy ON tenant_memberships;
CREATE POLICY membership_tenant_policy ON tenant_memberships
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
-- Membership verification must use a narrowly privileged service path.
-- Never allow users to select their own tenant solely through request headers.
