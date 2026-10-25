# Active property discovery and attributed claims — implementation plan

Baseline: main efeab78 (API 0.3.0); no open PRs at inventory. The active apps/api package and public schema remain authoritative. Root oydp is a separate reference backend, not an interchangeable service.

## Bounded implementation

1. Add bounded keyset pagination with timestamp/UUID tie-breakers, strict cursor validation and per-user/tenant/resource cursor scope. Cursors are navigation data, never authorization credentials; every page rechecks database authorization.
2. List only creator-owned or currently granted properties. Lock delegated grants used by a page so revocation serializes with active reads. Do not return total counts across inaccessible records.
3. Add an append-only property_claims ledger. Only the current creator with owner/editor membership and signed MFA may record a claim. Attribute author, property, tenant and timestamp on the server. Every claim stays user_claim/unverified; client fields cannot manufacture official verification.
4. Commit each claim and claim-linked audit event in one transaction. Read claims only after the same parent-property access checks, with bounded pagination. No editing/deletion, documents, write delegation or official source observations in this slice.
5. Export the active OpenAPI contract, run negative/security/pagination/upgrade tests against native PostgreSQL, preserve the 87-test reference suite, update status/evidence in the PR, and merge only on green current-head checks.

## Acceptance and limitations

Tests must cover empty/tied/multi-page results, inserted rows between pages, malformed/cross-scope cursors, same-/cross-tenant denial, grant expiry/revocation, read-only recipients, MFA/role downgrade, immutable claims, forged verification metadata, audit rollback and tenant/claim integrity. Existing migrations keep their checksums. Existing record data is preserved by additive migration 007. UI/provider onboarding and all remaining engines remain open; no production approval or public deployment implied.

## Implemented contracts — API 0.4.0

- GET `/v1/properties?limit=25&cursor=...` returns `items` and nullable `next_cursor`. Limits are 1–100; ordering is newest timestamp then UUID, both descending. A missing cursor starts at the newest visible record. No global count is returned.
- POST `/v1/properties/{id}/claims` accepts only `statement` (1–10,000 nonblank characters). Only the creator with a current owner/editor role and issuer-signed MFA may append. Each accepted POST creates a new claim; there is no automatic retry deduplication in this slice.
- GET `/v1/properties/{id}/claims?limit=25&cursor=...` returns the same page envelope, newest recorded timestamp/UUID first. Creators and current read grantees may read; forbidden/missing parent properties both return 404. Read grants never authorize writing claims.
- Claim output includes server-authored tenant/property/author/time, fixed `kind=user_claim`, and fixed `verification_status=unverified`. Statements are untrusted plain text, not legal verification, instructions, or authority to change data. Clients must render them as text.

`apps/api/openapi.json` is the exported active contract. Run `PYTHONPATH=apps/api:. python scripts/export_active_openapi.py` to regenerate, or append `--check` to detect drift. CI checks it against the active application. The root `docs/openapi.json` remains the separately identified reference backend's contract.

## Pagination and transaction semantics

Cursors are canonical bounded base64 JSON positions scoped to the user, tenant, endpoint and parent property. They are not signed secrets or authorization tokens. Reconstructing a cursor cannot bypass RLS; each page applies current membership/property grants. Invalid or accidentally cross-context cursors return 422 without echoing values. Timestamp/UUID tie-breakers avoid duplicates when timestamps tie. New records inserted above a cursor appear only after refresh; pagination is not a frozen cross-request snapshot.

The property page uses a bounded materialized grant CTE with shared locks, plus an explicit creator/grant predicate and RLS. Claim pages hold the parent read-grant lock. Revocation waits for those transactions to complete, then later reads are denied. Expiry is checked by PostgreSQL. The application ends database dependencies at function scope so commits complete before an HTTP success is sent; a deferred commit-failure test guards against false 201 responses. SQL and commit failures return generic 503 errors with no claim text or credentials.

## Storage and upgrade

Additive checksum migration 007 creates `public.property_claims`, private append/read RLS and page indexes. It preserves existing properties, evidence assertions, grants and audit history. A composite audit/claim foreign key enforces matching tenant and property even on privileged paths. Runtime has SELECT/INSERT only on claims, no mutation or deletion capability. Claim and audit inserts commit or roll back together; audit events store a claim ID rather than duplicating private statement text.

Apply migrations 001–007 and re-run runtime provisioning before API 0.4.0. Roll application code back only to a compatible private-access version (0.3.0); preserve ledger/history and applied migration files. No destructive down migration is provided. Older generic evidence is not silently reclassified into this claim ledger. Data deletion/redaction/retention, correction linkage, request idempotency and an independent audit sink require separate reviewed work before real-data production use.

## Current verification

Local active unit/API checks: 43 passed. Native PostgreSQL acceptance cases are authored and pending CI; skipped local database cases do not count as passing. CI must also preserve the full root reference suite, dependency audit, compilation and contract check before merge.
