CREATE TABLE IF NOT EXISTS evidence_assertions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  property_id uuid NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
  assertion_type text NOT NULL CHECK (length(assertion_type) BETWEEN 1 AND 100),
  assertion_text text NOT NULL,
  source_kind text NOT NULL CHECK (source_kind IN ('user_claim','professional_review','official_observation')),
  source_reference text,
  observed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (source_kind <> 'official_observation' OR source_reference IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS assertions_property_idx ON evidence_assertions(tenant_id, property_id);
ALTER TABLE evidence_assertions ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_assertions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS assertion_tenant_policy ON evidence_assertions;
CREATE POLICY assertion_tenant_policy ON evidence_assertions
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    AND EXISTS (SELECT 1 FROM properties p WHERE p.id = property_id AND p.tenant_id = evidence_assertions.tenant_id))
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    AND EXISTS (SELECT 1 FROM properties p WHERE p.id = property_id AND p.tenant_id = evidence_assertions.tenant_id));
-- source_kind is a classification of submitted evidence, NOT an attestation by OYDP.
