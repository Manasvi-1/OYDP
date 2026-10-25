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
