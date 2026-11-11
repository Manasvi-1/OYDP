# Implementation status

Controlling product scope: `docs/reference/06-25_OYDP_Master_Consolidated_Blueprint-1-.txt`. Supporting: `docs/ENGINE_REGISTER.md`, `docs/ROADMAP.md`, `docs/implementation/*`.

Status labels: `NOT_STARTED` | `IN_PROGRESS` | `IMPLEMENTED` | `TESTED` | `VERIFIED` | `BLOCKED` | `DEFERRED`.  
Evidence labels for surfaces: planned / UI prototype / static mockup / placeholder / generated source / executable implementation / integration-tested / production-hardened / independently reviewed.

Updated: 2026-11-11. Branch evidence: `feat/interview-demo-workspace` (post-merge with `origin/main`).

## Surface status

| Surface | Evidence label | Task status | Notes |
| --- | --- | --- | --- |
| E01 Property Identity API | executable implementation / integration-tested (partial) | VERIFIED (CI history) + TESTED (units this session) | API 0.12.0 |
| Tenant RLS + membership | integration-tested (CI) | VERIFIED in CI; local DB BLOCKED | |
| OIDC JWKS validation | executable implementation | TESTED (units) | Live IdP BLOCKED |
| MFA freshness + SF-008 | executable implementation | TESTED (units + route gates) | Live emission BLOCKED |
| Cross-tenant IDOR matrix | integration-tested (CI @ fc25eed+) | VERIFIED in CI; local BLOCKED | File restored onto feature branch via merge |
| Documents quarantine/encryption | executable implementation | TESTED (units); CI history for ACL | Scanner BLOCKED |
| Audit outbox/ledger | executable implementation | VERIFIED in CI history | External WORM DEFERRED |
| E03 diligence (bounded) | executable implementation (partial) | TESTED in CI history | Not offers/legal conclusions |
| `apps/web` workspace | executable implementation (partial) | IN_PROGRESS / TESTED (web CI + local unit history) | Cookie handoff in PR #22 |
| E02, E04–E13 | planned | NOT_STARTED | Bounded launch commitments retained |
| Root reference backend | frozen | DEFERRED (do not evolve) | |

## Task register

| Task ID | Phase | Priority | Description | Dependencies | Engines | Files / surfaces | DB | API | FE | Security | Tests | Acceptance | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T-AUDIT-001 | 0 | P0 | Repository audit + engineering ledger docs | None | All (governance) | `docs/engineering/*` | n/a | n/a | n/a | Honest labels | Doc review | Docs exist, claims match git/CI | IMPLEMENTED | This session |
| T-SEC-008 | 0 | P0 | Restore SF-008 MFA zero-age production guard onto interview branch | Merge `origin/main` | E01 | `apps/api/app/auth.py`, `main.py`, `test_auth.py` | n/a | Y | n/a | Config fail-closed | unit | Zero age rejected without `OYDP_OIDC_DEV_HTTP=1` | TESTED | Merge `ed7b5b7` + 126 unit pass |
| T-SEC-007 | 0 | P0 | Restore cross-tenant IDOR suite on interview branch | Merge `origin/main` | E01 | `tests/integration/test_z_cross_tenant_idor.py` | Y | Y | n/a | IDOR denials | integration CI | Suite present; CI history 223@fc25eed | VERIFIED local+CI | 8/8 local + CI |
| T-NEXT-001 | 0 | P0 | Local disposable PG full active suite | Portable PG or Docker | E01 | `apps/api/tests` + `tests/integration` | Y | Y | n/a | RLS/IDOR | integration | 238 pass 0 skip | VERIFIED | Portable PG 16.15 @ 55432 |
| T-E01-GRAPH-1 | 1 | P1 | Optional claim→source citation | T-NEXT-001 | E01 | `015_claim_source_attribution.sql`, `main.py` | Y | Y | optional | MFA + withdrawn gate | unit+integration | Claims stay unverified; withdrawn/foreign denied | VERIFIED | PR #25 |
| T-NEXT-004 | 1 | P1 | Document↔claim/source attribution | 015 | E01 | `016_document_attribution.sql`, attribution route | Y | Y | optional | MFA + RLS | unit+integration | Links set; scan/verification unchanged | VERIFIED | PR #27 @ 82df32e |
| T-NEXT-005 | 1 | P1 | Document↔identifier + export attribution refs | 016 | E01 | `017_document_identifier_attribution.sql`, attribution/export | Y | Y | optional | MFA + RLS | unit+integration | Current identifier only; export refs; title_verified false | VERIFIED | PR #28 @ 116bde9 |
| T-NEXT-006 | 1 | P1 | Review↔claim attribution | 015/012 | E01 | `018_review_claim_attribution.sql`, review route/export | Y | Y | optional | MFA + RLS | unit+integration | Unverified claim only; title_effect none | TESTED | 240 local pass @ 55432 |
| T-SEC-009 | 0 | P1 | HTTP route MFA gates without MFA dependency override | SF-008 | E01 | `apps/api/tests/test_mfa_route_gates.py` | stub authz only | Y | n/a | Negative MFA/auth_time | unit | pwd-only / missing / stale / zero-age → 403/503 | TESTED | 10/10 passed |
| T-WEB-022 | 0 | P1 | Keep OIDC session cookies on callback NextResponse | Web OIDC | E01 | `apps/web` callback/auth | n/a | n/a | Y | Session cookie handoff | web CI / e2e scripts | Sign-in reaches `/connect` on loopback | TESTED (CI) | PR #22 |
| T-SEC-003 | 1 | P2 | Production malware scanner adapter | Scanner infra | E01 | `documents.py` | Y | Y | Y | Fail-closed until pass | integration | Real adapter + CI | BLOCKED | SF-003 |
| T-SEC-006 | 0 | P2 | Live IdP enrollment + session kill on membership change | Docker/IdP | E01 | Keycloak/OIDC | Y | Y | Y | Live tokens | live script | Provider issues `auth_time` | BLOCKED | SF-006; no Docker |
| T-E01-GRAPH | 1 | P2 | Complete evidence graph beyond current identifiers/reviews/export | E01 slice | E01 | API + DB | Y | Y | Y | Provenance | integration | Graph journeys | NOT_STARTED | ENGINE_REGISTER Partial |
| T-E03-FULL | 2 | P3 | Full transaction/legal workspace | E01/E03 diligence | E03 | TBD | Y | Y | Y | Deterministic policy | e2e | Offers/payments out of scope until designed | NOT_STARTED | Diligence only today |
| T-E02…E13 | 2–4 | P3 | Remaining engines as bounded launches | Foundation | E02–E13 | TBD | Y | Y | Y | Per-engine | e2e | No silent drop | NOT_STARTED | ROADMAP |
| T-GA-GATES | 5 | P0 (later) | External security, legal, privacy, ops, commercial gates | All | All | — | — | — | — | Independent review | multi | Signed release decision | NOT_STARTED | PRODUCTION_READINESS |

## Next eligible task after this session

See `BUILD_LEDGER.md`. After T-NEXT-006 lands: remaining review↔document/identifier edges or PostGIS IDOR when Docker is available; do not fake scanner pass.
