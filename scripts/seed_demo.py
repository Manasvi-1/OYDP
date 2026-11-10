"""Reset and seed a disposable synthetic OYDP demo database.

Refuses to run unless:
  - OYDP_DEMO_SEED_ALLOW=yes
  - DEMO_DATABASE_URL (or TEST_DATABASE_URL) names a database containing demo, e2e, or test

Creates fictional tenants/subjects/properties only. Does not disable authentication,
bypass the API for ordinary users, or seed shared/production databases.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.migrate import migrate, provision_runtime  # noqa: E402


FIXED_TENANT = uuid.UUID('11111111-1111-4111-8111-111111111111')
OTHER_TENANT = uuid.UUID('22222222-2222-4222-8222-222222222222')
PROP_A = uuid.UUID('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')
PROP_B = uuid.UUID('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')
PROP_C = uuid.UUID('cccccccc-cccc-4ccc-8ccc-cccccccccccc')
REQUEST_A = uuid.UUID('dddddddd-dddd-4ddd-8ddd-dddddddddddd')


def require_disposable_dsn() -> str:
    if os.getenv('OYDP_DEMO_SEED_ALLOW') != 'yes':
        raise SystemExit('Refusing to seed: set OYDP_DEMO_SEED_ALLOW=yes')
    dsn = os.environ.get('DEMO_DATABASE_URL') or os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        raise SystemExit('Set DEMO_DATABASE_URL or TEST_DATABASE_URL to a disposable database')
    name = dsn.rsplit('/', 1)[-1].split('?', 1)[0].lower()
    if not any(marker in name for marker in ('demo', 'e2e', 'test')):
        raise SystemExit('Refusing to seed a database whose name is not marked disposable (demo|e2e|test)')
    return dsn


def truncate_public(conn: psycopg.Connection) -> None:
    conn.execute("""
      DO $$
      DECLARE stmt text;
      BEGIN
        SELECT 'TRUNCATE TABLE ' || string_agg(format('%I.%I', schemaname, tablename), ', ')
               || ' RESTART IDENTITY CASCADE'
          INTO stmt
        FROM pg_tables
        WHERE schemaname = 'public' AND tablename <> 'schema_migrations';
        IF stmt IS NOT NULL THEN
          EXECUTE stmt;
        END IF;
      END $$;
    """)


def seed(conn: psycopg.Connection) -> None:
    truncate_public(conn)
    conn.execute(
        """
        INSERT INTO tenant_memberships(tenant_id, subject_id, role) VALUES
          (%s, 'alice', 'owner'),
          (%s, 'reader', 'viewer'),
          (%s, 'mallory', 'owner')
        """,
        (FIXED_TENANT, FIXED_TENANT, OTHER_TENANT),
    )
    conn.execute(
        """
        INSERT INTO properties(id, tenant_id, label, jurisdiction, created_by) VALUES
          (%s, %s, '[SYNTHETIC] Indiranagar candidate plot', 'Bengaluru Urban', 'alice'),
          (%s, %s, '[SYNTHETIC] Whitefield warehouse shell', 'Bengaluru Urban', 'alice'),
          (%s, %s, '[SYNTHETIC] Other-tenant private lot', 'Hyderabad', 'mallory')
        """,
        (PROP_A, FIXED_TENANT, PROP_B, FIXED_TENANT, PROP_C, OTHER_TENANT),
    )
    conn.execute(
        """
        INSERT INTO property_claims(tenant_id, property_id, statement, kind, verification_status, created_by)
        VALUES
          (%s, %s, 'Seller described a 30 by 40 site. User-submitted and unverified.', 'user_claim', 'unverified', 'alice'),
          (%s, %s, 'Broker said khata transfer is pending. Unverified claim only.', 'user_claim', 'unverified', 'alice')
        """,
        (FIXED_TENANT, PROP_A, FIXED_TENANT, PROP_B),
    )
    conn.execute(
        """
        INSERT INTO property_identifiers(tenant_id, property_id, scheme, identifier_value, version, status, recorded_by)
        VALUES (%s, %s, 'survey', 'SYN-12/3', 1, 'current', 'alice')
        """,
        (FIXED_TENANT, PROP_A),
    )
    conn.execute(
        """
        INSERT INTO diligence_requests(id, tenant_id, property_id, title, body, status, created_by)
        VALUES (%s, %s, %s, 'Ask for the packet', 'List the papers you hold. Workspace request only.', 'open', 'alice')
        """,
        (REQUEST_A, FIXED_TENANT, PROP_A),
    )
    conn.execute(
        """
        INSERT INTO diligence_notes(tenant_id, property_id, request_id, body, created_by)
        VALUES (%s, %s, %s, 'Reader note: packet index is incomplete. Not a legal conclusion.', 'alice')
        """,
        (FIXED_TENANT, PROP_A, REQUEST_A),
    )


def main() -> None:
    dsn = require_disposable_dsn()
    applied = migrate(dsn)
    password = os.environ.get('RUNTIME_DATABASE_PASSWORD')
    if password:
        provision_runtime(dsn, password)
    with psycopg.connect(dsn) as conn:
        seed(conn)
        conn.commit()
    print('Applied migrations:', ', '.join(applied) or 'none already applied')
    print('Synthetic demo seed complete.')
    print('Tenant (alice owner):', FIXED_TENANT)
    print('Other tenant (mallory):', OTHER_TENANT)
    print('Readable alice properties:', PROP_A, PROP_B)
    print('All labels are fictional and prefixed [SYNTHETIC].')
    print('Authentication is unchanged; mint a real access token for alice to use the workspace.')


if __name__ == '__main__':
    main()
