-- Transactional outbox for audit events. The row is inserted by a definer trigger
-- in the same transaction as the event. Delivery state is append-only after a
-- successful mark. The payload is identifiers and event type only; claim text
-- is not copied. This is not an independent immutable log.
CREATE TABLE public.audit_outbox (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 event_id uuid NOT NULL UNIQUE REFERENCES public.property_audit_events(id) ON DELETE CASCADE,
 tenant_id uuid NOT NULL,
 property_id uuid NOT NULL,
 event_type text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 delivered_at timestamptz,
 attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0)
);
CREATE INDEX audit_outbox_pending_idx ON public.audit_outbox (created_at, id) WHERE delivered_at IS NULL;
ALTER TABLE public.audit_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY outbox_private_read ON public.audit_outbox FOR SELECT USING (
 tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id=audit_outbox.tenant_id AND p.id=audit_outbox.property_id)
);

INSERT INTO public.audit_outbox(event_id, tenant_id, property_id, event_type, created_at)
SELECT id, tenant_id, property_id, event_type, created_at FROM public.property_audit_events;

CREATE FUNCTION public.enqueue_audit_outbox() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog, pg_temp AS $$
BEGIN
  INSERT INTO public.audit_outbox(event_id, tenant_id, property_id, event_type)
  VALUES (NEW.id, NEW.tenant_id, NEW.property_id, NEW.event_type);
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.enqueue_audit_outbox() FROM PUBLIC;

CREATE TRIGGER enqueue_audit_outbox
AFTER INSERT ON public.property_audit_events
FOR EACH ROW EXECUTE FUNCTION public.enqueue_audit_outbox();

CREATE FUNCTION public.protect_delivered_audit() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog, pg_temp AS $$
BEGIN
  IF OLD.delivered_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'delivered audit is immutable' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER protect_delivered_audit
BEFORE UPDATE ON public.audit_outbox
FOR EACH ROW EXECUTE FUNCTION public.protect_delivered_audit();
