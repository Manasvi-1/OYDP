# PR4 implementation audit and next increment

Baseline: main 542cc8973e2d8e9650eb90ffde141940c133e2ce, 25 October 2026.
All 85 source blobs were retrieved through the GitHub connection and verified against Git blob SHA-1 hashes. No open PRs were returned before starting this increment.

## Verified existing implementation

- `apps/api/app/main.py`: actual FastAPI property creation/discovery/detail, read grant/revocation, attributed immutable claim creation/history. SQL-backed handlers, not canned success responses.
- `apps/api/app/auth.py`: configured JWKS signature validation, issuer/audience/time/subject checks and signed MFA requirement.
- `infra/db/001...007`: actual schema, forced RLS, current membership/private property rules, composite lineage and claim constraints.
- `scripts/migrate.py`, bootstrap, Dockerfile and compose: executable backend/database setup. This audit did not execute Docker startup locally.
- `tests/integration/test_database.py`: native database authorization, rollback and concurrency coverage. Unit auth tests use controlled keys/mocks; they do not prove live-provider integration.
- `oydp/` and root `migrations/`: separate reference implementation. Its test counts do not prove the active service has those features.

Merged-head CI was independently queried: API smoke 40203737809, Database security 40203737721 and foundation checks 40203737728 all concluded success. Dependabot dependency graph remained queued and is not application acceptance evidence.

Fresh local execution: 48 active unit tests passed with one existing TestClient deprecation warning; active OpenAPI drift check passed. All 85 retrieved blobs match baseline Git hashes. Native PostgreSQL/PostGIS tests were not rerun locally (server absent); earlier merged-head CI supplies that evidence.

## Missing at baseline

No `apps/web`, Next.js application, browser journey or browser sign-in existed. Real provider onboarding/MFA freshness, secure documents, independent audit delivery, correction/deletion/export, and the remaining engine journeys remain pending. Plans and source specifications are not completed product features. No production approval or independent security assessment is claimed.

## Next increment: first private property workspace (draft)

`apps/web/app/page.js` implements actual API-driven create/list/detail, claim append/history pagination, read grant/revoke, disconnect and error states. There is no seeded property data, synthetic login or fabricated verification badge. Claims render as escaped text. Tokens are held in memory, never browser persistent storage. All permissions remain enforced by the API/database.

`apps/web/lib/proxy.mjs` forwards an explicit route/method allowlist to an operator-configured fixed origin, passes only bearer/tenant/JSON headers, bounds incoming bodies, disables caching/redirects, and sanitizes upstream infrastructure errors. Six executable Node tests passed locally, including denied authentication, tenant validation, path rejection and error leakage.

This is an operator session-token preview, not completed OIDC browser sign-in. Manual access-token entry is a temporary integration boundary. Secure Authorization Code + PKCE/provider onboarding and provider-backed browser acceptance are required before treating it as customer-ready.

First frontend CI run 40206746435 passed installation, six proxy tests, Next production build and high-severity production dependency audit. Dependency lock is now committed and CI uses npm ci. Added a Playwright browser journey against the actual API and native PostgreSQL, including create/claim persistence, escaped user text, grant/revoke, reader write denial, cross-tenant membership denial and MFA denial. The test harness supplies an ephemeral signing key in place of JWKS network transport; production signature/claim validation, API handlers and RLS execute unchanged. This is synthetic identity transport, not live-provider verification. Browser acceptance on the updated head and live-provider validation remain required. Do not mark roadmap frontend complete until those checks pass. Fresh reference API/policy/provenance subset: 50 passed plus 13 subtests; reference database suite was not rerun locally.

Future increments must use the same evidence rule: source implementation + executable behavior checks + linked CI evidence; explicitly list unresolved external integration and release gates.

## Follow-up source and runtime audit

Reviewed PR #5 baseline 75b372c82e398c9440876b080a59f8283d47553e. Retrieved all 100 tracked source blobs; 98 unchanged files matched Git blob hashes after transfer normalization, and the two proxy implementation/test files were intentionally changed. No TODO/FIXME/NotImplemented/placeholder markers or bare pass statements were found in apps, infra, scripts or oydp; this search is supporting evidence, not proof of feature completeness.

Inspected actual SQL-backed handlers, JWKS authentication, migrations, frontend API calls, proxy implementation and CI/browser tests. Local checks passed: 48 active API unit tests; 50 reference API/foundation tests plus 13 subtests; eight proxy tests; Next.js production build; active OpenAPI drift and Python compilation. One existing TestClient deprecation warning remains. Native PostgreSQL/PostGIS and browser integration evidence comes from GitHub Actions, not local execution.

Follow-up commit f5083ba6740a9dbe8aa8dacb76924176fe33f52b bounds decoded upstream responses at 8 MiB, validates JSON/UTF-8, cancels oversized streams and adds executable failure-path tests. Updated engine/security descriptions to remove stale claims that property grants or all UI were absent. Browser sign-in, evidence graph and other engine commitments remain pending.

Prior frontend head 75b372c passed all four application workflows, including native database/browser persistence and denial checks. Follow-up API smoke, database security and reference foundation workflows have passed; final web workflow must also pass on the current PR head before merge. Consult current PR checks for final-head evidence rather than treating historical results as current acceptance.
