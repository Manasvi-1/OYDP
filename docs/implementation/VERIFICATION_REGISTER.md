# OYDP verification register

**Audit date:** 2026-10-25 (UTC+05:30). **Scope:** GitHub branch feat/property-identity-foundation, PR #2.

## Evidence levels
- VERIFIED: linked executable check or directly inspected GitHub artifact.
- AUTHORED: code/test committed but runtime outcome not established.
- PENDING: not implemented or not independently assessed.
- BLOCKED: prerequisite or approval missing.

| Control | State | Evidence / limitation |
| --- | --- | --- |
| Repository tracked in GitHub | VERIFIED | Private Manasvi-1/OYDP; development branch and draft PR #2 |
| API smoke test job | VERIFIED | GitHub Actions run 40196819003, job 121179329024, conclusion success; pytest command succeeded |
| Full application functional test suite | PENDING | Smoke tests cover only health and fail-closed endpoints |
| Property routes fail closed without OIDC | VERIFIED within smoke scope | API smoke job includes tests asserting HTTP 503; not a deployed service validation |
| PostgreSQL migration application | PENDING | SQL files committed; no successful database migration evidence |
| Tenant RLS cross-tenant negative tests | PENDING | Policies drafted; no integration-test execution evidence |
| OIDC signature/issuer/audience verification | PENDING | Not integrated |
| Production-safe runtime database role | PENDING | Not provisioned or verified |
| Evidence provenance correctness | PENDING | Schema drafted, no end-to-end verification |
| Consent, revocation, deletion, export | PENDING | Not implemented |
| Malware scanning and encrypted evidence storage | PENDING | Not implemented |
| Independent audit trail and restore drill | PENDING | Not implemented |
| Dependency and vulnerability assessment | PENDING | No reviewed security scan evidence |
| External penetration test | PENDING | No external assessment |
| Legal/data-rights approval | PENDING | No signed reviewer evidence |
| Reviewer approval for PR #2 | BLOCKED | Copilot review comments reported quota exhaustion, not approval |
| All 13 engine journeys | PENDING | No full engine acceptance evidence |
| Production release approval | PENDING | Not authorized |

## Source records
- PR: https://github.com/Manasvi-1/OYDP/pull/2
- Workflow run: https://github.com/Manasvi-1/OYDP/actions/runs/40196819003
- Job: https://github.com/Manasvi-1/OYDP/actions/runs/40196819003/job/121179329024

## Required verification before merge
1. Capture CI result on the latest PR head SHA, not an older successful commit.
2. Execute actual PostGIS migrations and tenant A/B isolation tests using a non-owner runtime role.
3. Verify OIDC token rejection and membership enforcement; remove the intentionally disabled endpoints only after these tests pass.
4. Add automated secret/dependency scanning and review findings.
5. Obtain a substantive human code review and explicit merge approval.
6. Reconcile README, roadmap and this register to the same commit SHA.

## Approval policy
GitHub Actions success is not a security certification or legal approval. No merge, production deployment or public release without the required owner approvals.


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

## Current authenticated API slice

Supersedes historical pending entries where explicitly implemented: RS256 access-token verifier, trusted database membership, property create/read and transactional append-only audit. Local execution: 24 API/auth tests passed; 24 real PostgreSQL cases not executed locally. Dependency audit reported no known vulnerabilities; hashed dependency lock and CI audit added. See PROPERTY_API.md. Latest-head CI acceptance remains pending until GitHub reports it.

The repository owner explicitly instructed pushing and merging in this development session. This authorizes merge of the tested pre-alpha slice; it is not an independent human/security review or production approval. Copilot quota failures remain non-approvals. GitHub-enforced protection rules must not be bypassed.

## Verified authenticated API execution — 25 October 2026

Implementation commit: `1cc439843c354d119222e243a5dd051df5b11d8c`.
[Database security CI](https://github.com/Manasvi-1/OYDP/actions/runs/40198550858): **48 passed, zero skipped**, one TestClient dependency deprecation warning. This includes 24 API/auth tests and 24 PostgreSQL/API integration cases.
[API and dependency audit CI](https://github.com/Manasvi-1/OYDP/actions/runs/40198550853): passed; hash-locked dependency installation and pip-audit succeeded with no known vulnerabilities reported.
All 36 tracked source files matched GitHub blob hashes before this evidence-only update. These results supersede pending CI status above for the tested implementation. This follow-up changes documentation only; its own checks must also pass before merge. Independent security/human review, live provider onboarding and production approval remain unfulfilled. One passing suite does not validate the whole platform.
