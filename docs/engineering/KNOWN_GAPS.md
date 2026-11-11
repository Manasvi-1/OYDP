# Known gaps

Honest unfinished / blocked / defective items. Prefer fixing security and foundation before engine expansion.

Updated: 2026-11-11.

## Blocked on external infrastructure or human action

| ID | Gap | Severity | Blocker | Workaround in product |
| --- | --- | --- | --- | --- |
| G-IDP | Live Keycloak/OIDC enrollment and `auth_time` emission verification | High | Docker/daemon unavailable on audit machine; no production IdP | DevOidc + synthetic JWKS unit tests; realm mapper present |
| G-SCAN | Production malware scanner adapter | Medium | No bundled AV product / paid service authorization | Fail-closed quarantine; download denied until `pass` |
| G-PG-LOCAL | Local disposable PostGIS via Docker Compose | Medium | Docker CLI absent; Desktop engine pipe unavailable | Mitigated: portable PostgreSQL 16.15 on 55432 ran full active suite (238 pass); Compose/Keycloak still blocked |
| G-REVIEW | Independent human/security review | High | Requires named reviewers | Self-review + automated negatives only |
| G-WORM | External immutable audit sink | Medium | Ops/infrastructure | In-DB ledger + outbox (superuser can disable triggers) |
| G-PRIVACY | Deletion, retention, legal hold, restore drills | High | Product/legal design incomplete | Not claimed |

## Code / coverage gaps (implementable without paid services)

| ID | Gap | Severity | Notes |
| --- | --- | --- | --- |
| G-MFA-INT | Many integration fixtures override `require_mfa=True` | Medium | Route-level unit gates added (`test_mfa_route_gates.py`); deepen DB-backed non-override cases when PG available |
| G-SESSION | No session kill on membership revoke | High (SF-006) | Grants checked per request; token revocation at IdP not wired |
| G-E01-GRAPH | Evidence graph incomplete vs blueprint | Medium | Claim→source live citation landed (`015`); document↔claim/source and fuller graph journeys still open |
| G-ENGINES | E02, E04–E13 not started | Scope | Must remain commitments; do not fake |
| G-THREAT-DOC | Threat model row for files was stale | Low | Corrected this session to reflect quarantine + BLOCKED scanner |
| G-WEB-DEPTH | Web consumes subset of API; engines UI is disclosure-only | Medium | Expected for pre-alpha |

## Recently closed on this branch line

| ID | Closure | Evidence |
| --- | --- | --- |
| Branch missing SF-008 / IDOR vs main | Merged `origin/main` | Commit `ed7b5b7` |
| HTTP MFA gates without MFA override | Added route tests | 10 passed |
| Interview OIDC cookie loss on callback | PR #22 commits | Web CI SUCCESS |

## Explicit non-goals this session

Deploy, paid cloud spend, merging when CI red, force-push, rewriting reference `oydp/` backend, claiming GA or independent audit.
