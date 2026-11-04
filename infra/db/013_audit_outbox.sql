-- Local delivery queue beside the append-only audit ledger.
-- The ledger still stamps delivered_at when the event is copied.
-- This outbox stays pending until scripts/deliver_audit.py marks it.
-- A database superuser can still disable triggers. This is not an external write-once store.
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
 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
 AND EXISTS (SELECT 1 FROM public.properties p WHERE p.tenant_id = audit_outbox.tenant_id AND p.id = audit_outbox.property_id)
);
REVOKE ALL ON public.audit_outbox FROM PUBLIC;

INSERT INTO public.audit_outbox(event_id, tenant_id, property_id, event_type, created_at)
SELECT id, tenant_id, property_id, event_type, created_at FROM public.property_audit_events;

CREATE FUNCTION public.enqueue_audit_outbox() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
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
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF OLD.delivered_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'delivered audit is immutable' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.protect_delivered_audit() FROM PUBLIC;

CREATE TRIGGER protect_delivered_audit
BEFORE UPDATE ON public.audit_outbox
FOR EACH ROW EXECUTE FUNCTION public.protect_delivered_audit();
