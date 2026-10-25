# Property Identity API — executable backend slice

This change implements property create/read, not the whole OYDP platform. Records are shared within a tenant; per-property invitations and granular grants are not implemented. Do not use this pre-alpha slice for real property documents or customer data.

## Contracts and trust boundaries

- `GET /healthz`: process liveness only, not database/provider readiness.
- `POST /v1/properties`: owner/editor only; body contains `label` and `jurisdiction`. Server assigns property and tenant IDs. Returns 201 with ID, tenant, label, jurisdiction and creation time.
- `GET /v1/properties/{uuid}`: any current tenant member; inaccessible/missing property returns 404.
- Both property routes require `Authorization: Bearer <access-token>` and `X-Tenant-ID: <uuid>`. The header selects a tenant; only the database membership authorizes it. Nonmembers receive 403.
- Missing configuration/database/provider outage fails with 503. Invalid tokens return 401. Invalid bodies/UUIDs return 422. Database details and tokens are never returned in errors.
- `/openapi.json` supplies the generated request/response contract. No update/delete/list or evidence-upload API is implied.

## Identity configuration

Set `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` to operator-controlled HTTPS endpoints and a dedicated API audience. Only RS256 JWT access tokens with `typ=at+jwt`, `kid`, `iss`, `aud`, `sub`, `iat`, `exp` are accepted. ID tokens and arbitrary token-directed JWKS URLs are rejected. Signature, issuer, audience, expiry, future issuance and optional not-before are checked with PyJWT. JWKS cache expires after five minutes; individual signing keys are not cached indefinitely. Network timeout is five seconds. Providers using opaque tokens or another token profile need an explicit reviewed adapter.

Tests use generated RSA keys and synthetic identities; no live provider has been configured or certified. MFA, interactive login, logout/token revocation and provider onboarding remain separate work. Membership revocation takes effect at the next request lookup; it does not cancel an in-flight authorized transaction.

## Database setup

Follow DATABASE_FOUNDATION.md to apply all migrations (now 001–005) and re-run runtime provisioning. Runtime credentials must be for `oydp_app`; privileged roles fail closed in the API. Provision memberships through the trusted migration/admin path, never through a client-selected role. A membership subject belongs to the single configured issuer; changing issuers requires migrating/revalidating memberships.

```bash
export PYTHONPATH=apps/api:.
python -m pip install --require-hashes -r apps/api/requirements.lock
python scripts/migrate.py --provision-runtime
uvicorn app.main:app --reload
```

Use synthetic property labels in development. `jurisdiction` is currently a bounded descriptive field, not proof of geographic coverage or official source availability.

## Audit and rollback

A property insert and `property.created` event commit in the same transaction. Runtime can append/read tenant audit events but cannot update/delete them. Audit insert failure rolls back the property. Database administrators remain trusted; external immutable delivery/outbox, read-access audit, retention and recovery drills remain pending. Do not claim a certified immutable audit service.

Migration 005 is additive. Roll back application code without deleting audit history; no destructive automatic down migration is supplied. Existing migrations retain their original checksums.

## Verification

Local command: `PYTHONPATH=apps/api:. python -m pytest -q apps/api/tests tests/integration`.
Local result: 24 passed; 24 PostgreSQL cases skipped because no local server is available. Skips do not count as acceptance. CI must run all 48 against a disposable PostgreSQL database. Dependency scan of requirements reported no known vulnerabilities locally; hash-pinned lock and CI audit are included. A dependency scan is not an independent security review.

Remaining release gates: real identity-provider integration, property-specific grants, UI, secret scanning, read audit, external audit delivery, documents/scanning/encryption, all remaining engines, independent review and production approval.

## Verified authenticated API execution — 25 October 2026

Implementation commit: `1cc439843c354d119222e243a5dd051df5b11d8c`.
[Database security CI](https://github.com/Manasvi-1/OYDP/actions/runs/40198550858): **48 passed, zero skipped**, one TestClient dependency deprecation warning. This includes 24 API/auth tests and 24 PostgreSQL/API integration cases.
[API and dependency audit CI](https://github.com/Manasvi-1/OYDP/actions/runs/40198550853): passed; hash-locked dependency installation and pip-audit succeeded with no known vulnerabilities reported.
All 36 tracked source files matched GitHub blob hashes before this evidence-only update. These results supersede pending CI status above for the tested implementation. This follow-up changes documentation only; its own checks must also pass before merge. Independent security/human review, live provider onboarding and production approval remain unfulfilled. One passing suite does not validate the whole platform.
