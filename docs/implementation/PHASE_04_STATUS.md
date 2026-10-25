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
