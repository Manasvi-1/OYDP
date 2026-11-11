# Repository audit

Evidence-backed audit of `Manasvi-1/OYDP`. Labels use only: planned, UI prototype, static mockup, placeholder, generated source, executable implementation, integration-tested, production-hardened, independently reviewed. Chat history is not evidence.

**Audit instant:** 2026-11-11 (session on `feat/interview-demo-workspace`).  
**Remote:** `https://github.com/Manasvi-1/OYDP.git` (private).  
**Default branch:** `main` @ `e149283` (Merge PR #21).  
**Working branch after reconcile:** `feat/interview-demo-workspace` @ merge `ed7b5b7` (interview cookie/e2e commits + `origin/main` security).

## Git and GitHub

| Item | Evidence |
| --- | --- |
| Open PR | [#22](https://github.com/Manasvi-1/OYDP/pull/22) Keep sign-in cookies on the callback response — OPEN, not draft, MERGEABLE, CI SUCCESS |
| PR #4 | MERGED (property discovery / claims) — historical |
| PR #5 | MERGED (private workspace; was draft at merge) — historical; later superseded by Launch-1 / interview workspace on main |
| Branch protection on `main` | **Not configured** (`gh api .../protection` → 404) |
| Recent CI | Active API smoke, Active database security, Reference foundation, web workspace — SUCCESS on PR #22 head prior to this session’s merge+tests |
| Issues | None open via `gh issue list` at audit time |

### Pre-reconcile defect (fixed in this session)

`feat/interview-demo-workspace` had diverged from `main` at merge-base `44ea471`. Commits present on main but absent on the tip included SF-008 MFA production config guard, `tests/integration/test_z_cross_tenant_idor.py`, and `scripts/secret_scan_light.py`. Merging PR #22 without first merging `main` into the branch would still have been a non-fast-forward combine on GitHub, but the tip itself was **defective relative to main** for local/security continuity. **Remediation:** `git merge origin/main` completed cleanly (no overlapping file conflicts with interview web changes).

## Classification A–G

| ID | Area | Classification | Evidence summary |
| --- | --- | --- | --- |
| A | Active Property Identity API (`apps/api` 0.16.0) | **real** / integration-tested (partial) | Private create/read/share, claims, corrections, write grants, documents quarantine, trusted evidence, attribution edges, evidence graph/conflicts, consents/export, audit outbox, diligence; audit append gated; OpenAPI check matches; unit suite executed this session |
| B | AuthN (OIDC JWKS RS256 `at+jwt`) | **real** (unit); live IdP **not independently verified** | `apps/api/app/auth.py`; loopback HTTP gated by `OYDP_OIDC_DEV_HTTP=1`; MFA `amr` + `auth_time`; SF-008 rejects `OYDP_MFA_MAX_AGE_SECONDS=0` outside loopback |
| C | AuthZ / tenant isolation / RLS | **real** / integration-tested in CI history | `infra/db` RLS + membership; IDOR matrix on main/CI (`test_z_cross_tenant_idor.py`); local native PG **blocked** this machine (no Docker / no `TEST_DATABASE_URL`) |
| D | Document ACL / quarantine | **real** fail-closed; scanner **placeholder/BLOCKED** | AES-GCM seal, quarantined insert, download only `scan_state=pass`; `get_document_scanner()` returns `None` |
| E | `apps/web` Property Intelligence Workspace | **real** / partial | Next.js OIDC loopback, httpOnly session cookies, property/evidence/diligence/audit UI; CSP; Playwright e2e scripts present; live Keycloak enrollment **BLOCKED** without Docker |
| F | Engines E02, E04–E13 | **planned** / missing product workflows | `docs/ENGINE_REGISTER.md`; web Engines page discloses Planned |
| G | Root `oydp/` + `migrations/` | **frozen reference** (PR #1) | `scripts/migrate.py` rejects root path; separately tested; not interchangeable with `apps/api` |

## Claim verification matrix

| Claim | Verdict | Notes |
| --- | --- | --- |
| DB persistence via `infra/db` | Verified in CI history; not re-run locally this session | Migrations `001`–`019`; role `oydp_app` |
| Clean migrations / checksum discipline | Executable control present | New migrations only under `infra/db` |
| Real OIDC validation | Executable + unit-tested | Synthetic JWKS ≠ live provider |
| Backend authz | Executable + negative unit/route tests | Route MFA gates added this session |
| Tenant isolation via direct API | CI-verified IDOR suite; local BLOCKED | Needs disposable PostGIS |
| Document ACL | Fail-closed executable | Production AV BLOCKED |
| Frontend ↔ backend | Partial executable | Proxy + server actions; e2e depends on local stack |
| Revocation | Executable grants revoke/expiry | Session kill on membership change still open (SF-006) |
| Clean install | Partial | Compose documented; Docker absent on this shell |
| Non-mocked tests | Unit real; many integration MFA overrides exist | Route MFA tests avoid MFA override |

## Active vs reference backends

| | Active | Reference |
| --- | --- | --- |
| Code | `apps/api` | `oydp/` |
| Migrations | `infra/db` | `migrations/` |
| Schema / role | `public` / `oydp_app` | `oydp` / `oydp_runtime` |
| Evolve? | Yes | Frozen |

## Maturity (honest)

Not production-hardened. Not independently reviewed. Not GA. Highest maturity surfaces: Property Identity API vertical slice and tenant RLS controls with CI history. Lowest: engines E02/E04–E13, live IdP, malware scanner, privacy/deletion/restore, external audit sink.
