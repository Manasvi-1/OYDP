-- G-SESSION / SF-006 partial: membership-revoke session posture without a live IdP.
-- not_before_epoch is floor(epoch)+1, so a token issued in the revoke second is stale.
-- The API rejects iat < not_before_epoch. IdP token revocation remains out of scope.
-- Follows 020_runtime_audit_and_source_gates.sql (merged via PR #38).

CREATE TABLE public.membership_session_invalidations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  subject_id text NOT NULL CHECK (length(subject_id) BETWEEN 1 AND 255 AND btrim(subject_id) = subject_id),
  invalidated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  not_before_epoch bigint NOT NULL CHECK (not_before_epoch >= 0),
  reason text NOT NULL CHECK (reason IN ('membership_revoked', 'session_kill')),
  actor_subject text NOT NULL CHECK (length(actor_subject) BETWEEN 1 AND 255 AND btrim(actor_subject) = actor_subject)
);
CREATE INDEX membership_session_invalidations_lookup_idx
  ON public.membership_session_invalidations (tenant_id, subject_id, not_before_epoch DESC);
ALTER TABLE public.membership_session_invalidations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.membership_session_invalidations FORCE ROW LEVEL SECURITY;
-- Subjects may read only their own invalidation rows under the active tenant.
CREATE POLICY membership_session_invalidations_self_read
  ON public.membership_session_invalidations FOR SELECT USING (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    AND subject_id = nullif(current_setting('app.subject_id', true), '')
  );
-- Inserts are only reachable from the security-definer helpers below. The runtime
-- role has no INSERT grant. WITH CHECK still constrains a non-superuser owner.
CREATE POLICY membership_session_invalidations_record
  ON public.membership_session_invalidations FOR INSERT WITH CHECK (
    tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
    AND actor_subject = nullif(current_setting('app.subject_id', true), '')
  );
REVOKE ALL ON public.membership_session_invalidations FROM PUBLIC;

CREATE FUNCTION public.reject_membership_session_rewrite()
RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  RAISE EXCEPTION 'Membership session invalidations are append-only' USING ERRCODE = '42501';
END $$;
REVOKE ALL ON FUNCTION public.reject_membership_session_rewrite() FROM PUBLIC;
CREATE TRIGGER membership_session_invalidations_no_rewrite
  BEFORE UPDATE OR DELETE ON public.membership_session_invalidations
  FOR EACH ROW EXECUTE FUNCTION public.reject_membership_session_rewrite();
CREATE TRIGGER membership_session_invalidations_no_truncate
  BEFORE TRUNCATE ON public.membership_session_invalidations
  FOR EACH STATEMENT EXECUTE FUNCTION public.reject_membership_session_rewrite();

CREATE FUNCTION public._record_membership_session_invalidation(
  t uuid, target text, actor text, reason text
) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  nbf bigint := floor(extract(epoch FROM clock_timestamp()))::bigint + 1;
BEGIN
  INSERT INTO public.membership_session_invalidations(
    tenant_id, subject_id, not_before_epoch, reason, actor_subject
  ) VALUES (t, target, nbf, reason, actor);
  RETURN nbf;
END $$;
REVOKE ALL ON FUNCTION public._record_membership_session_invalidation(uuid, text, text, text) FROM PUBLIC;

CREATE FUNCTION public.revoke_tenant_membership(t uuid, target text)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  actor text := nullif(current_setting('app.subject_id', true), '');
  target_role text;
  owner_count integer;
  nbf bigint;
BEGIN
  IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid
     OR actor IS NULL OR target IS NULL
     OR length(target) NOT BETWEEN 1 AND 255 OR btrim(target) = '' OR btrim(target) <> target
     OR target = actor THEN
    RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
  -- One lock per tenant so two owners cannot revoke each other and leave zero owners.
  PERFORM pg_advisory_xact_lock(hashtextextended('oydp-membership/' || t::text, 0));
  PERFORM 1 FROM public.tenant_memberships
    WHERE tenant_id = t AND subject_id = actor AND role = 'owner' FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
  SELECT role INTO target_role FROM public.tenant_memberships
    WHERE tenant_id = t AND subject_id = target FOR UPDATE;
  IF target_role IS NULL THEN
    RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
  IF target_role = 'owner' THEN
    SELECT count(*)::integer INTO owner_count FROM public.tenant_memberships
      WHERE tenant_id = t AND role = 'owner';
    IF owner_count <= 1 THEN
      RAISE EXCEPTION 'Cannot revoke the last tenant owner' USING ERRCODE = 'P0001';
    END IF;
  END IF;
  DELETE FROM public.tenant_memberships WHERE tenant_id = t AND subject_id = target;
  nbf := public._record_membership_session_invalidation(t, target, actor, 'membership_revoked');
  RETURN nbf;
END $$;
REVOKE ALL ON FUNCTION public.revoke_tenant_membership(uuid, text) FROM PUBLIC;

CREATE FUNCTION public.invalidate_tenant_member_sessions(t uuid, target text)
RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
  actor text := nullif(current_setting('app.subject_id', true), '');
  nbf bigint;
BEGIN
  IF t IS DISTINCT FROM nullif(current_setting('app.tenant_id', true), '')::uuid
     OR actor IS NULL OR target IS NULL
     OR length(target) NOT BETWEEN 1 AND 255 OR btrim(target) = '' OR btrim(target) <> target
     OR target = actor THEN
    RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended('oydp-membership/' || t::text, 0));
  PERFORM 1 FROM public.tenant_memberships
    WHERE tenant_id = t AND subject_id = actor AND role = 'owner' FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
  PERFORM 1 FROM public.tenant_memberships
    WHERE tenant_id = t AND subject_id = target FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Resource unavailable' USING ERRCODE = 'P0002';
  END IF;
  nbf := public._record_membership_session_invalidation(t, target, actor, 'session_kill');
  RETURN nbf;
END $$;
REVOKE ALL ON FUNCTION public.invalidate_tenant_member_sessions(uuid, text) FROM PUBLIC;

-- Upgrade path when the runtime role already exists. Fresh roles get the same grants
-- from scripts/migrate.py provision_runtime after this migration is applied.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'oydp_app') THEN
    REVOKE ALL ON TABLE public.membership_session_invalidations FROM oydp_app;
    GRANT SELECT ON TABLE public.membership_session_invalidations TO oydp_app;
    GRANT EXECUTE ON FUNCTION public.revoke_tenant_membership(uuid, text) TO oydp_app;
    GRANT EXECUTE ON FUNCTION public.invalidate_tenant_member_sessions(uuid, text) TO oydp_app;
    REVOKE ALL ON FUNCTION public._record_membership_session_invalidation(uuid, text, text, text) FROM oydp_app;
    REVOKE ALL ON FUNCTION public.reject_membership_session_rewrite() FROM oydp_app;
  END IF;
END $$;
