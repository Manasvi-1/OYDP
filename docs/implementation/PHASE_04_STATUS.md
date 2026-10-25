# Phase 04 — implementation status

This branch begins the Property Identity foundation. It is **not** a functional property application.

## Added
- FastAPI health endpoint and intentionally fail-closed property routes.
- Initial PostgreSQL properties table with forced row-level security.
- Basic smoke and fail-closed tests.

## Required before enabling property routes
1. Integrate OIDC signature, issuer, audience and expiry verification.
2. Resolve verified tenant membership server-side (never from untrusted tenant headers).
3. Provision a dedicated non-owner runtime DB role without BYPASSRLS.
4. Execute migrations and verify forced RLS using two separate tenant fixtures.
5. Add provenance assertions, identifiers, audit outbox and migration rollback.
6. Add a Next.js app, local Compose services and CI; run tests and document results.
7. Obtain approval before public deployment.

No official property source integrations or legal ownership verification are implemented.


## Database foundation update — 25 October 2026

See [database implementation and acceptance](DATABASE_FOUNDATION.md) for migration tooling, runtime-role provisioning, composite tenant integrity, 13 PostgreSQL tests and the dedicated CI job. Local API tests: 3 passed; database tests: 13 skipped pending PostgreSQL execution. Earlier unverified items remain open unless this record explicitly supersedes them. OIDC and property CRUD remain disabled.

## Verified GitHub execution — 25 October 2026

Tested implementation commit: `11fda6b59992e7f333c040565c0ccb8ffcd507df`.
[Database security run #1](https://github.com/Manasvi-1/OYDP/actions/runs/40197718274)
completed successfully on PostgreSQL 16.15 and Python 3.12.15: **16 passed,
0 skipped, 1 dependency deprecation warning** (13 database + 3 API tests).
[API smoke run #18](https://github.com/Manasvi-1/OYDP/actions/runs/40197718445)
also completed successfully. JUnit artifact: `database-security-results`,
artifact ID `12600403784`. These results supersede the pending-CI status above
for this exact implementation commit. They do not constitute OIDC, full platform,
independent security review or production approval.

Known maintenance debt: FastAPI/Starlette warns about the httpx TestClient
integration; GitHub also reports older action runtimes. Dependency locking,
audit and reviewed action upgrades remain follow-up work.

## Authenticated API slice — current update

Supersedes earlier disabled-route status: property create/read, verified JWT access tokens, trusted membership lookup and transactional audit are implemented. See [API contracts, setup and limitations](PROPERTY_API.md). Local result: 24 API/authentication tests passed, 24 PostgreSQL cases await CI. Runtime tests must pass on the current PR head before merge. No UI, live identity-provider setup or production release is claimed.

## Verified authenticated API execution — 25 October 2026

Implementation commit: `1cc439843c354d119222e243a5dd051df5b11d8c`.
[Database security CI](https://github.com/Manasvi-1/OYDP/actions/runs/40198550858): **48 passed, zero skipped**, one TestClient dependency deprecation warning. This includes 24 API/auth tests and 24 PostgreSQL/API integration cases.
[API and dependency audit CI](https://github.com/Manasvi-1/OYDP/actions/runs/40198550853): passed; hash-locked dependency installation and pip-audit succeeded with no known vulnerabilities reported.
All 36 tracked source files matched GitHub blob hashes before this evidence-only update. These results supersede pending CI status above for the tested implementation. This follow-up changes documentation only; its own checks must also pass before merge. Independent security/human review, live provider onboarding and production approval remain unfulfilled. One passing suite does not validate the whole platform.

## API 0.3.0 private-read access update

See CANONICAL_PROPERTY_ACCESS.md: new creator-private records, MFA-gated creation/sharing/revocation, 30-day read grants, atomic access audit and populated migration upgrade tests. This supersedes earlier tenant-shared behavior. PR #1 is merged with both backend histories preserved; its root implementation remains separately identified. Current-head CI is required before accepting the new access slice. Live provider setup, write delegation, claims/UI and independent security/release review remain open.
