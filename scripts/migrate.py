"""Transactional, checksum-verified migrations. Run with an owner DSN, never runtime credentials."""
import argparse
import hashlib
from pathlib import Path
import os

import psycopg

ROOT = Path(__file__).resolve().parents[1] / 'infra' / 'db'


def migrate(dsn, directory=ROOT):
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
        conn.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON properties, evidence_assertions TO oydp_app')
        conn.execute('REVOKE ALL ON tenant_memberships, schema_migrations FROM oydp_app')
        conn.execute('GRANT SELECT ON tenant_memberships TO oydp_app')
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
