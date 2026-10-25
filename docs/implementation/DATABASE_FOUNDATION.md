# Database foundation: implementation and acceptance

## Inventory and scope

Baseline inspected: b7b06c75c5b76e21ce140c6b6b9e4fdbdedeb76e.
The baseline contains three SQL files, disabled property API routes, three API
smoke tests, and no migration runner or database integration tests.

This change implements the database foundation portion of E01. OIDC, property
CRUD, property-level grants, audit outbox and the web interface remain open.
All 13 engines remain release commitments. No production/security approval is implied.

## Implemented

- Ordered transactional migrations, advisory lock, checksum ledger, drift and
  out-of-order rejection; failure rolls back the transaction.
- Separate runtime role without ownership, role inheritance or RLS bypass.
  Membership writes and migration-ledger access are withheld.
- Composite tenant/property foreign key protects evidence lineage even when
  privileged ingestion bypasses RLS.
- Membership SELECT requires subject and tenant; no self-service membership writes.
- Thirteen real PostgreSQL acceptance tests plus an isolated PostgreSQL 16 CI job.

## Run locally

Use a disposable database for tests. Integration fixtures create synthetic records;
they are not safe to run against a populated or production database.

```bash
pip install -r apps/api/requirements.txt
export MIGRATION_DATABASE_URL='postgresql://OWNER:SECRET@localhost:5432/oydp'
export RUNTIME_DATABASE_PASSWORD='at-least-24-random-characters'
python scripts/migrate.py --provision-runtime
# Set DATABASE_URL separately to the oydp_app connection; never use the owner DSN.
export TEST_DATABASE_URL='postgresql://OWNER:SECRET@localhost:5432/EMPTY_TEST_DATABASE'
PYTHONPATH=apps/api:. python -m pytest -q apps/api/tests tests/integration
```

Provisioning is a privileged operator command. Passwords are read from the
environment and never printed. The DSN owner must be allowed to create roles.
Migration and runtime credentials must never be interchangeable.

## Security boundary and limitations

Transaction settings are server-controlled authorization context, not credentials.
A runtime SQL connection can set these values: RLS limits accidental unscoped
queries but does not protect against arbitrary SQL execution or stolen credentials.
OIDC verification, server-side membership resolution and property permissions must
be implemented before enabling API routes. Membership subjects must be namespaced
by the configured issuer when identity integration is added.

No down migration is supplied: deleting property/evidence data automatically would
be destructive. Apply in staging first; use an operator-reviewed forward repair or
restore a tested backup on failure. Existing evidence with invalid tenant lineage
will make migration 004 fail atomically and requires investigation.

## Verification record — 25 October 2026

Local command: `PYTHONPATH=oydp/apps/api:oydp /tmp/oydp-venv/bin/python -m pytest -q oydp/apps/api/tests oydp/tests`.
Result: **3 passed, 13 skipped** (no local PostgreSQL service). The database tests
are authored but not yet verified at this point. GitHub CI must provide actual
PostgreSQL results on the commit under review; skipped tests are not a pass.

## Next implementation order

1. Verify database CI and correct failures.
2. Add OIDC signature/issuer/audience/expiry verification and negative token tests.
3. Resolve membership using verified identity; enforce reader/editor permissions.
4. Implement property create/read and audit events in one transaction.
5. Add API integration tests with two tenants and revoked membership.
6. Build the Next.js property workspace only against the verified contract.
