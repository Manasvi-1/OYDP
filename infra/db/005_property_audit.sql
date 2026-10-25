-- Transactional append-only application audit; privileged DB administrators remain trusted.
CREATE TABLE property_audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    property_id uuid NOT NULL,
    actor_subject text NOT NULL,
    event_type text NOT NULL CHECK (event_type = 'property.created'),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, property_id) REFERENCES properties(tenant_id, id)
);
ALTER TABLE property_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE property_audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_read ON property_audit_events FOR SELECT
    USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY audit_append ON property_audit_events FOR INSERT
    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
        AND actor_subject = nullif(current_setting('app.subject_id', true), ''));
