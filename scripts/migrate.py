"""Transactional, checksum-verified migrations. Run with an owner DSN, never runtime credentials."""
import argparse
import hashlib
from pathlib import Path
import os

import psycopg

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / 'infra' / 'db'
# PR #1 reference tree. Never apply it through this script against the active public schema.
REFERENCE_MIGRATIONS = REPO / 'migrations'


def migrate(dsn, directory=ROOT):
    directory = Path(directory).resolve()
    if directory == REFERENCE_MIGRATIONS.resolve():
        raise ValueError(
            'Root migrations/ is the PR #1 reference tree; use infra/db for the active API'
        )
    files = sorted(directory.glob('[0-9][0-9][0-9]_*.sql'))
    if not files:
        raise ValueError('No migrations found')
    versions = [p.name.split('_')[0] for p in files]
    if len(versions) != len(set(versions)):
        raise ValueError('Duplicate migration version')
    applied = []
    with psycopg.connect(dsn) as conn:
        # One transaction and advisory lock prevent partially applied/concurrent runs.
        conn.execute('SELECT pg_advisory_xact_lock(78653421)')
        conn.execute('CREATE TABLE IF NOT EXISTS public.schema_migrations (name text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())')
        existing = dict(conn.execute('SELECT name, checksum FROM public.schema_migrations').fetchall())
        available = {p.name for p in files}
        if set(existing) - available:
            raise ValueError('Applied migration missing from source')
        for path in files:
            content = path.read_text(encoding='utf-8')
            digest = hashlib.sha256(content.encode()).hexdigest()
            if path.name in existing:
                if existing[path.name] != digest:
                    raise ValueError('Applied migration checksum mismatch: ' + path.name)
                continue
            if existing and path.name < max(existing):
                raise ValueError('Out-of-order migration: ' + path.name)
            conn.execute(content, prepare=False)
            conn.execute('INSERT INTO public.schema_migrations(name, checksum) VALUES (%s, %s)', (path.name, digest))
            applied.append(path.name)
    return applied


def provision_runtime(dsn, password):
    if len(password) < 24:
        raise ValueError('Runtime password must contain at least 24 characters')
    from psycopg import sql
    with psycopg.connect(dsn) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='oydp_app'").fetchone():
            conn.execute('CREATE ROLE oydp_app LOGIN')
        conn.execute(sql.SQL('ALTER ROLE oydp_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Literal(password)))
        # Refuse inherited privileges or ownership instead of silently accepting an unsafe role.
        if conn.execute("SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='oydp_app')").fetchone():
            raise ValueError('Runtime role must have no role memberships')
        if conn.execute("SELECT 1 FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname='oydp_app')").fetchone():
            raise ValueError('Runtime role must not own relations')
        conn.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        conn.execute('GRANT USAGE ON SCHEMA public TO oydp_app')
        conn.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON properties TO oydp_app')
        # Legacy evidence_assertions is frozen; trusted evidence uses SECURITY DEFINER helpers.
        conn.execute('REVOKE ALL ON evidence_assertions FROM oydp_app')
        conn.execute('GRANT SELECT ON evidence_assertions TO oydp_app')
        conn.execute('REVOKE ALL ON tenant_memberships, schema_migrations FROM oydp_app')
        conn.execute('GRANT SELECT ON tenant_memberships TO oydp_app')
        conn.execute('GRANT UPDATE(subject_id) ON tenant_memberships TO oydp_app')
        conn.execute('REVOKE ALL ON property_read_grants FROM oydp_app')
        conn.execute('GRANT SELECT, UPDATE(subject_id) ON property_read_grants TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.set_property_read_access(uuid,uuid,text,timestamptz) TO oydp_app')
        conn.execute('REVOKE ALL ON property_write_grants FROM oydp_app')
        conn.execute('GRANT SELECT, UPDATE(subject_id) ON property_write_grants TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.set_property_write_access(uuid,uuid,text,timestamptz) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.correct_property(uuid,uuid,text,text) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.actor_has_live_write_grant(uuid,uuid) TO oydp_app')
        conn.execute('REVOKE ALL ON property_corrections FROM oydp_app')
        conn.execute('GRANT SELECT ON property_corrections TO oydp_app')
        conn.execute('REVOKE ALL ON property_audit_events FROM oydp_app')
        # Audit rows append only through SECURITY DEFINER helpers (never direct INSERT).
        conn.execute('GRANT SELECT ON property_audit_events TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.record_property_created_audit(uuid,uuid) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.record_document_quarantined_audit(uuid,uuid,uuid) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.record_diligence_audit(uuid,uuid,text) TO oydp_app')
        conn.execute('REVOKE ALL ON property_claims FROM oydp_app')
        # Claims are append-only through record_property_claim so source citations stay gated.
        conn.execute('GRANT SELECT ON property_claims TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.record_property_claim(uuid, uuid, text, uuid) TO oydp_app')
        conn.execute('REVOKE ALL ON property_documents FROM oydp_app')
        conn.execute('GRANT SELECT (id, tenant_id, property_id, created_by, media_type, byte_size, sha256, scan_state, created_at, scanned_at, claim_id, source_id, identifier_id) ON property_documents TO oydp_app')
        conn.execute('GRANT INSERT ON property_documents TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.record_document_scan(uuid,uuid,uuid,text,bytea) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.load_quarantined_document(uuid,uuid,uuid) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.load_document_ciphertext(uuid,uuid,uuid) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.attribute_property_document(uuid,uuid,uuid,uuid,uuid,uuid) TO oydp_app')
        # Trusted evidence is readable by the runtime role and writable only through the functions below.
        # The role cannot insert its own ledger rows or call the trigger and edit-check functions.
        conn.execute('REVOKE ALL ON property_identifiers, evidence_sources, professional_reviews, property_consents, tenant_audit_events, audit_ledger FROM oydp_app')
        conn.execute('GRANT SELECT ON property_identifiers, evidence_sources, professional_reviews, property_consents, tenant_audit_events, audit_ledger TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.record_property_identifier(uuid,uuid,text,text,text) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.register_evidence_source(uuid,text,text,text) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.withdraw_evidence_source(uuid,uuid,text) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.record_professional_review(uuid,uuid,text,text,uuid,uuid,uuid,uuid) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.record_property_consent(uuid,uuid,text) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.revoke_property_consent(uuid,uuid,text) TO oydp_app')
        conn.execute('GRANT EXECUTE ON FUNCTION public.authorize_property_export(uuid,uuid) TO oydp_app')
        conn.execute('REVOKE ALL ON FUNCTION public.actor_can_edit_property(uuid,uuid) FROM oydp_app')
        conn.execute('REVOKE ALL ON FUNCTION public.ledger_row_must_match_outbox() FROM oydp_app')
        conn.execute('REVOKE ALL ON FUNCTION public.copy_property_audit() FROM oydp_app')
        conn.execute('REVOKE ALL ON FUNCTION public.copy_tenant_audit() FROM oydp_app')
        conn.execute('REVOKE ALL ON FUNCTION public.reject_ledger_rewrite() FROM oydp_app')
        conn.execute('REVOKE ALL ON audit_outbox FROM oydp_app')
        conn.execute('GRANT SELECT ON audit_outbox TO oydp_app')
        conn.execute('REVOKE ALL ON FUNCTION public.enqueue_audit_outbox() FROM oydp_app')
        conn.execute('REVOKE ALL ON FUNCTION public.protect_delivered_audit() FROM oydp_app')
        conn.execute('REVOKE ALL ON diligence_requests, diligence_notes FROM oydp_app')
        conn.execute('GRANT SELECT, INSERT ON diligence_requests, diligence_notes TO oydp_app')
        conn.execute('GRANT UPDATE (status, closed_at) ON diligence_requests TO oydp_app')
        conn.execute("ALTER ROLE oydp_app SET search_path = public")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provision-runtime', action='store_true')
    args = parser.parse_args()
    dsn = os.environ['MIGRATION_DATABASE_URL']
    print('Applied:', ', '.join(migrate(dsn)) or 'none')
    if args.provision_runtime:
        provision_runtime(dsn, os.environ['RUNTIME_DATABASE_PASSWORD'])
        print('Runtime role provisioned')
