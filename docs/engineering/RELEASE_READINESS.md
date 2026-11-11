# Release readiness

**Verdict: NOT ready for GA / production release.**

Updated: 2026-11-12.

## Gate checklist

| Gate | State | Evidence |
| --- | --- | --- |
| Functional vertical slice (E01 partial + bounded E03) | Partial pass | API 0.15.0 + web workspace (graph/conflicts reads); not all blueprint E01 journeys |
| All 13 engine end-to-end workflows | FAIL | E02, E04–E13 planned only |
| Live IdP enrollment | FAIL / BLOCKED | SF-006 |
| MFA freshness in production IdP tokens | FAIL / BLOCKED | Code ready; live unverified |
| Document malware scanning | FAIL / BLOCKED | SF-003 |
| Tenant isolation continuous verification | Partial | CI history; local PG blocked this session |
| Independent security review | FAIL | None |
| Privacy / deletion / restore | FAIL | Not implemented |
| External immutable audit | FAIL | App ledger only |
| Legal / data rights approvals | FAIL | Pending |
| Ops SLOs / restore drills | FAIL | Pending |
| Commercial / paid pilot validation | FAIL | Pending |
| Signed cross-functional release decision | FAIL | Pending |

## What may be demonstrated

Private pre-alpha Property Identity workspace on loopback with synthetic or local-dev identity, with honest unverified claim labeling and fail-closed document quarantine. Interview demo scripts under `docs/interview/` describe that posture.

## What must not be claimed

- Production-hardened or independently reviewed
- Government affiliation, title verification, guaranteed valuation/returns/approvals
- Complete 13-engine product
- Live Keycloak enrollment completed on machines without a running provider
