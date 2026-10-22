# Current milestone note — 23 October 2026

The original 21 October record below is historical. See `VALIDATION.md` and `IMPLEMENTATION_PLAN.md` for the current backend slice. PT-002 now has PostgreSQL migrations and restricted-role embedded database tests; PT-003 has repository/API enforcement; PT-005 persists user claims with atomic audit events. Native PostgreSQL/PostGIS checks, managed OIDC, file quarantine, Next.js UI, source registry, and pilot validation remain incomplete. No Sprint 1 completion is claimed.

---

# Sprint 1 execution record

Date: 21 October 2026. Scope follows roadmap document 17, pages 3–4. Status is deliberately based on runnable evidence, not documentation volume.

| Ticket | Current evidence | Remaining exit work |
|---|---|---|
| PT-001 Identity | Policy accepts trusted subject, active tenant membership and MFA state | Evaluate managed OIDC vendors; JWT signature/issuer/audience/expiry validation; invite binding; real integration spike |
| PT-002 Database | Architecture choice preserved | PostgreSQL/PostGIS schema; reversible migration; isolated tenant runtime role; RLS including WITH CHECK; real DB up/down and isolation tests |
| PT-003 Authorization | Executable policy; positive and negative unit tests pass | Wire every repository/API operation; policy matrix for all roles; stale session and concurrent revocation integration tests |
| PT-004 Evidence | Scan-state gate and threat model | MIME sniffing, size caps, encrypted quarantine, actual scanner, fail-closed worker, download delivery and retention |
| PT-005 Provenance | Validated assertion model separates claim/observation/review/unknown | Persistent source registry, dated source snapshots, conflicts/corrections, atomic audit outbox |
| PT-006 Rule registry | Requirements captured below | Jurisdiction-bound versions, reviewer approval, effective dates, withdrawal and supported-region gates |
| PT-012 Pilot validation | No evidence supplied | Founder-led professional interviews, consented notes and signed interest; no messages sent |

## Ordered implementation queue

1. Draft schema around tenants, memberships, property candidates, identifiers, source revisions, assertions, grants, evidence objects and audit outbox. Every child relationship must prevent tenant/property substitution with composite keys or equivalent constraints.
2. Apply and reverse migrations on a real disposable PostgreSQL/PostGIS instance. Test with the restricted runtime role, not a superuser or table owner. Include connection-pool tenant-context reset checks.
3. Implement FastAPI property candidate and assertion operations with verified OIDC context. Grants come from server-side state; tenant selection never establishes membership. Unknown objects and forbidden objects must avoid existence leaks.
4. Connect an API-backed UI for the first vertical slice. No synthetic government records or fake integration success.
5. Add encrypted upload quarantine, real scanner transitions, document-scoped grants, revocation-safe delivery and audit outbox. Avoid long-lived URLs that outlive revocation requirements.
6. Complete all first-slice integration and end-to-end tests before expanding engine workflows.

## Rule/source approval requirements

Record jurisdiction, source origin and revision, effective/expiry dates, access rights and redistribution constraints, approval identity/date and withdrawal reason. Unknown rights or missing approval disables authoritative retrieval. A source URL does not constitute a data license. Published legal statements require current independent review; none are verified by this package.

## Working decisions

ADR-001: modular monolith; 13 separate microservices are unnecessary at this stage.
ADR-002: no legal ownership status is derived from account role, user-uploaded evidence, a hash, or a professional-review label.
ADR-003: explicit per-object grants; membership alone does not confer property access. The initial policy requires MFA for all writes and document downloads, a conservative implementation choice pending identity design.
ADR-004: all 13 engines remain GA scope. Initial development order does not reduce that commitment.
ADR-005: resolve source ambiguity conservatively and record missing inputs. Do not mark external approvals complete on the basis of generated documents.

## Validation record

Python 3.12.14: `python3 -m unittest discover -s tests -v` passed 18 tests on 21 October 2026. No database, HTTP, browser, provider or cloud checks have been run. No psql, Docker or pytest executable was found by the initial environment probe; domain checks use the standard library. Database tooling must be provisioned before PT-002 validation. The workstation's WSL state remains unconfirmed and independent of this hosted workspace.
