# OYDP — Own Your Dream Property

Private development workspace for a property evidence and lifecycle platform. The first backend slice creates property candidates, records explicitly unverified user claims, and keeps access scoped to current memberships and property grants.

**Status: tested backend foundation; not a completed Sprint 1 or production application.** All 13 engines remain launch commitments. No government integration, title certification, customer-data service or public deployment is enabled.

## What runs

- FastAPI: create/list/read property candidates and record user claims; generated OpenAPI contract.
- PostgreSQL: forced tenant RLS, composite foreign keys, current membership checks, explicit property grants, and business writes committed atomically with audit outbox events.
- Authentication: pinned RS256 verification, issuer/audience/expiry checks, UUID subject and issuer-provided `mfa` authentication-method check for writes.
- Existing domain policy: document-scoped download/scan-state gate and attributed provenance models. These remain domain logic; file delivery is not implemented.

The API uses PostgreSQL, not an in-memory repository. Test fixtures are synthetic and never represent official property records. A user claim cannot promote itself to verified evidence.

## Run tests

Python 3.12+, preferably in a virtual environment:

```bash
python -m venv .venv
# Linux/WSL: source .venv/bin/activate
# Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Without database DSNs, integration tests are explicitly skipped. For a disposable, empty PostgreSQL database, provision a separate `oydp_runtime` login (non-owner, no superuser/BYPASSRLS), then set `OYDP_TEST_ADMIN_DSN`, `OYDP_TEST_RUNTIME_DSN`, and `OYDP_TEST_ALLOW_RESET=yes`. The integration suite creates and drops only the `oydp` schema; never point it at real data. CI includes a disposable PostgreSQL/PostGIS service.

See [validation evidence](docs/VALIDATION.md) for actual checks and limitations. A CI configuration is not evidence of a successful CI run.

## Local database and API

1. Set `OYDP_LOCAL_DB_ADMIN_PASSWORD` to a strong local-only secret, then `docker compose up -d postgres`. The database port binds to loopback. Do not use this Compose file as a production deployment.
2. Set `OYDP_ADMIN_DATABASE_URL`, `OYDP_RUNTIME_DB_PASSWORD` and `OYDP_LOCAL_BOOTSTRAP=yes`. Run `python scripts/bootstrap_db.py` once against the new local DB. The script creates the restricted role, PostGIS and schema; it refuses an existing schema. If interrupted after role creation, inspect state before retrying.
3. Provision approved membership rows through an administrator connection. There is no self-enrollment or default authorized account. The tenant and subject UUIDs must match the configured identity issuer's mapped subjects.
4. Configure `OYDP_DATABASE_URL` using the restricted runtime login, `OYDP_JWT_PUBLIC_KEY_FILE`, `OYDP_JWT_ISSUER` (HTTPS), and `OYDP_JWT_AUDIENCE`. Do not pass the administrator DSN to the API. The public key is pinned by the operator; automatic JWKS/key rotation and the provider login flow remain to be integrated.
5. Start: `python -m uvicorn oydp.api:app_from_env --factory --host 127.0.0.1 --port 8000`.

Requests need `Authorization: Bearer <provider-issued-token>` and `X-Tenant-ID: <tenant-uuid>`. The tenant header selects context; it does not grant membership. `GET /health/live` checks process liveness only, not database readiness. `GET /openapi.json` returns the contract. Interactive docs are disabled.

## Scope and security boundaries

RLS is a tenant boundary, while per-property grants are enforced by repository operations. Database credentials and transaction context are trusted server inputs, never client-controlled SQL. Runtime cannot update/delete audit records; the outbox is **not** an independently immutable audit sink. Authorized administrators can alter the database.

Property creation issues explicit creator read/write grants for 30 days. Grant renewal, invitations and administrative revocation interfaces remain pending. Each request checks current database state. Write paths lock membership and relevant grants for their transaction; native PostgreSQL concurrent revocation testing remains required.

Missing and forbidden property requests both return 404. Claims have no automatic legal authority. Jurisdiction defaults to `unresolved`; free text does not validate an administrative boundary. UUID subjects and `amr: ["mfa"]` require an explicit identity-provider contract. JWT verification alone is not a full OIDC integration.

Still required: Next.js UI and visual QA, managed OIDC login/JWKS rotation and MFA freshness, evidence encryption/scanning/delivery, source approvals, consent/export/deletion, idempotency, edge body/rate limits, DB timeouts/pooling, observability, independent audit delivery, backup/restore, PostGIS geometry, and all remaining engine journeys. The shared design-context link was inaccessible during this milestone, so no visual fidelity or frontend completion is claimed.

Read [implementation plan](docs/IMPLEMENTATION_PLAN.md), [threat model](docs/THREAT_MODEL.md), and [engine register](docs/ENGINE_REGISTER.md). Changes belong on feature branches and require review before merge or release.
