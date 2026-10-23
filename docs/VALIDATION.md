# Verification record — 23 October 2026

## Actually executed

- Original ZIP baseline: 18 standard-library tests passed before edits.
- Current sharing increment, local Python suite: **84 passed, 3 native-concurrency tests skipped, 13 subtests passed** in 1.56 seconds.
- Prior native foundation CI: **60 passed, 13 subtests passed**, PostgreSQL 17.5 with PostGIS and a restricted login, including concurrent membership/grant revocation. [Run 39874641464](https://github.com/Manasvi-1/OYDP/actions/runs/39874641464), commit `36314eabbca636d2bd580382ea8d8b0c532f91c4`. Current sharing increment native result will be recorded after CI.
- Embedded PostgreSQL engine: PostgreSQL 18.6 / PGlite 0.5.11. The SQL ran through psycopg over a loopback socket, with `SET ROLE oydp_runtime` in the test harness. Production code has no embedded database mode.
- API-to-database path: RS256-signed synthetic identity -> authenticated create -> persisted read -> user claim -> audit events -> cross-tenant denial.
- Negative checks: wrong signature/issuer/audience/algorithm, expired/future-issued tokens, malformed subject/AMR, missing MFA, forged request fields, invalid pagination, no grants, inactive membership, revoked/expired grants, cross-tenant reads/inserts/references, and attempted claim promotion/audit deletion.
- Migration up, down, re-apply, down succeeded against the disposable database.
- Audit-insert failure rolled back property and initial grants.
- Transaction-local tenant context cleared on commit.
- Runtime membership/grant reassignment was denied while required read locks succeeded.
- Sharing checks: read/write/downgrade/revoke journey, unchanged-request audit deduplication, no collaborator resharing, same-tenant active recipients, no self-targeting, expiry bounded by creator grant, revoked access denial, and atomic audit failure rollback.
- Migration 002 rollback succeeds before sharing history and refuses to discard existing access audit history. Function permissions and fixed search path are asserted.
- OpenAPI regenerated from API version 0.3.0 with `PYTHONPATH=. python scripts/export_openapi.py`.
- `python -m compileall -q oydp tests scripts`: passed.
- `python -m pip check`: no broken requirements found.

One test-client warning remains: Starlette deprecates its httpx adapter in favor of httpx2. Requests passed; this warning is not suppressed.

## Reproduce embedded tests

```bash
python -m pip install -r requirements-dev.txt
npm ci --prefix tools/embedded-db
bash scripts/test_embedded.sh
```

Use an available loopback port 55432. The harness creates a new in-memory database and terminates it on exit. It uses synthetic data only. PGlite's socket detach can race the next connection: the harness retries **connection establishment only**, at most five attempts, and never retries SQL/assertions. Native tests do not use this retry or SET ROLE shim.

## Evidence limits

Native PostgreSQL binaries and Docker were unavailable locally. Installing the OS database package failed due to environment permissions. PGlite supports PostgreSQL execution but is single-connection and does not prove native concurrent revocation behavior or native login authentication; those require the separately recorded GitHub CI results. Neither test environment proves PostGIS product functionality, durability after process restart, or production performance.

No customer-facing UI, browser E2E, managed identity-provider integration, encryption/scanner pipeline, independent immutable audit delivery, penetration test, live government integration, legal validation or deployment was completed. All 13 engine acceptance journeys remain launch gates.

## Issues found and corrected

- RLS row-lock reads require UPDATE visibility. Added narrowly scoped visibility policies with `WITH CHECK(false)` so runtime reads can lock while updates remain denied.
- Initial embedded socket reconnects were occasionally rejected during teardown; test-only connection retries resolve that transport limitation without masking SQL errors.

This record demonstrates a backend increment, not completion of the application or Sprint 1.
