-- A foreign key must enforce tenant lineage even for privileged ingestion paths.
ALTER TABLE properties ADD CONSTRAINT properties_tenant_id_id_key UNIQUE (tenant_id, id);
ALTER TABLE evidence_assertions ADD CONSTRAINT assertions_tenant_property_fk
  FOREIGN KEY (tenant_id, property_id) REFERENCES properties(tenant_id, id) ON DELETE RESTRICT;
-- Membership is selected by BOTH verified identity and selected tenant.
DROP POLICY membership_tenant_policy ON tenant_memberships;
CREATE POLICY membership_tenant_policy ON tenant_memberships FOR SELECT
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    AND subject_id = nullif(current_setting('app.subject_id', true), ''));
-- No INSERT/UPDATE/DELETE policy: membership administration is a separate privileged path.
