# Known gaps

Honest unfinished / blocked / defective items. Prefer fixing security and foundation before engine expansion.

Updated: 2026-11-12.

## Blocked on external infrastructure or human action

| ID | Gap | Severity | Blocker | Workaround in product |
| --- | --- | --- | --- | --- |
| G-IDP | Live Keycloak/OIDC enrollment and `auth_time` emission verification | High | Docker/daemon unavailable on audit machine; no production IdP | DevOidc + synthetic JWKS unit tests; realm mapper present |
| G-SCAN | Production malware scanner adapter | Medium | No bundled AV product / paid service authorization | Fail-closed quarantine; download denied until `pass` |
| G-PG-LOCAL | Local disposable PostGIS via Docker Compose | Medium | Docker CLI absent; Desktop engine pipe unavailable | Mitigated for non-PostGIS: portable PostgreSQL 16.15 on 55432 runs full active suite; **T-NEXT-009 PostGIS IDOR remains BLOCKED** until Docker/PostGIS available |
| G-REVIEW | Independent human/security review | High | Requires named reviewers | Self-review + automated negatives only |
| G-WORM | External immutable audit sink | Medium | Ops/infrastructure | In-DB ledger + outbox (superuser can disable triggers) |
| G-PRIVACY | Deletion, retention, legal hold, restore drills | High | Product/legal design incomplete | Not claimed |

## Code / coverage gaps (implementable without paid services)

| ID | Gap | Severity | Notes |
| --- | --- | --- | --- |
| G-MFA-INT | Many integration fixtures override `require_mfa=True` | Medium | Route-level unit gates added (`test_mfa_route_gates.py`); deepen DB-backed non-override cases when useful |
| G-SESSION | No session kill on membership revoke | High (SF-006) | Grants checked per request; token revocation at IdP not wired |
| G-E01-GRAPH | Evidence graph incomplete vs blueprint | Medium | Attribution edges + read-only graph + conflict signals landed; human adjudication / dedup workflows still open |
| G-ENGINES | E02, E04–E13 not started | Scope | Must remain commitments; do not fake |
| G-THREAT-DOC | Threat model row for files was stale | Low | Corrected earlier to reflect quarantine + BLOCKED scanner |
| G-WEB-DEPTH | Web consumes subset of API; engines UI is disclosure-only | Medium | Graph/conflicts on main; CSP + attribution write/display on PR #38 (`T-NEXT-012`); engines UI remains disclosure-only |
| G-RATELIMIT | Process-local mutation throttle only | Medium | Not multi-worker / not edge; do not claim production DDoS protection |
| G-PG-INT | Migration 020 + attribution negatives need disposable PG | High | `TEST_DATABASE_URL` unset; Docker absent on this machine |

## Recently closed on this branch line

| ID | Closure | Evidence |
| --- | --- | --- |
| Branch missing SF-008 / IDOR vs main | Merged `origin/main` | Commit `ed7b5b7` |
| HTTP MFA gates without MFA override | Added route tests | 10 passed |
| Interview OIDC cookie loss on callback | PR #22 commits | Web CI SUCCESS |
| Claim→source / document / review attribution + graph projection | PRs #25–#33 | Active API 0.14.0 on main |
| Evidence conflicts + export sources + web graph/conflicts UI | PRs #35–#37 | API 0.15.0; web PR #37 |
| Web CSP middleware unwired (`proxy.js` unused by Next 15) | This branch / PR #38 | `middleware.js` + build manifest matchers |
| Direct audit INSERT + legacy assertions DML + editor-wide source withdraw | This branch | Migration `020` + API 0.16.0 |

## Explicit non-goals this session

Deploy, paid cloud spend, merging when CI red, force-push, rewriting reference `oydp/` backend, claiming GA or independent audit. Do not stall the project on **T-NEXT-009** while Docker remains unavailable.
