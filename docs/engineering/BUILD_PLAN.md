# OYDP build plan

**Audience:** Manasvi (software engineer)  
**Repo:** [Manasvi-1/OYDP](https://github.com/Manasvi-1/OYDP)  
**Audit date:** 2026-11-26  
**Audit workspace:** `c:\Users\WorkstationAdmin\OYDP-disposition-wt`  
**Controlling scope:** `docs/reference/06-25_OYDP_Master_Consolidated_Blueprint-1-.txt` (see `docs/reference/manifest.json`)  
**Execution standard:** `.cursor/rules/oydp-master.mdc` and `AGENTS.md`

This plan is grounded only in repository evidence (code, migrations, docs, tests, CI, PRs, Git history). Maturity labels use only: `planned`, `UI prototype`, `static mockup`, `placeholder`, `generated source`, `executable implementation`, `integration-tested`, `production-hardened`, `independently reviewed` — and only when evidence supports them.

**Do not treat this document as production approval, GA readiness, or independent security review.**

---

## 1. Current state audit summary

### Git / remote

| Item | Evidence |
| --- | --- |
| Remote | `origin` → `https://github.com/Manasvi-1/OYDP.git` |
| Default branch | `main` |
| Audit branch | `feat/property-dedup-candidates` (tracks `origin/main` at `b9acf7f`) |
| Tip of `origin/main` | `b9acf7f` — Merge PR #44 (`docs/build-ledger-pr43-close`) |
| Latest product merge on main | PR #43 — evidence conflict dispositions (API + web); merge `5c103b3` |
| Working tree | **Dirty.** Dedup candidates (API 0.20.0, migration 023, web `/dedup`) exist locally; many modified + untracked files; **not yet committed/pushed** at audit time |

### What is real vs planned

| Layer | Reality |
| --- | --- |
| Active product backend | `apps/api` + `infra/db` — Property Identity API **0.20.0** on this dirty branch (main tip still reflects post-#43 / #44 docs close; README badge still says **0.19.0**) |
| Frozen reference backend | `oydp/` + root `migrations/` — PR #1 Property Foundation **0.3.0**; schema `oydp`, role `oydp_runtime`, UUID subjects. **Do not evolve as the product path.** `scripts/migrate.py` rejects applying root `migrations/` |
| Web | `apps/web` — authenticated Next.js private property workspace (OIDC/session, CSP, E01 surfaces, bounded diligence, engines disclosure page). Local **untracked** `/dedup` on this branch |
| Engines | **E01** deep partial; **E03** bounded diligence only; **E02, E04–E13** planned (no product workflows) |
| Production / GA | Explicitly **not** ready (`docs/engineering/RELEASE_READINESS.md`, `docs/implementation/PRODUCTION_READINESS.md`, root README) |

### Active vs reference backend (dual-backend trap)

| | Active | Reference (frozen) |
| --- | --- | --- |
| Code | `apps/api` | `oydp/` |
| Migrations | `infra/db/` (001–022 on main; **023 untracked** on this branch) | `migrations/*.up.sql` / `*.down.sql` |
| Schema / DB role | `public` / `oydp_app` | `oydp` / `oydp_runtime` |
| Subjects | string OIDC `sub` | UUID `sub` |
| Auth | JWKS URL (`OIDC_*`) | pinned JWT public key |
| CI acceptance | `api-smoke.yml` + `database-security.yml` (+ `web.yml` if FE touched) | `checks.yml` (PostGIS) — **not** active-API acceptance |
| Tests | `PYTHONPATH=apps/api:. pytest apps/api/tests tests/integration` | `PYTHONPATH=. pytest tests/test_api.py tests/test_database.py tests/test_foundation.py` |

**Rule:** Never treat green reference CI as active acceptance. Never sync data between trees. Never rewrite `oydp/` to “catch up.”

### Web / PR #5 preservation

- PR #5 (`feat/private-property-workspace`) is **merged historical** foundation for the authenticated Next.js workspace.
- Agent contract: preserve untracked local `apps/web` work and PR #5 lineage; do not overwrite frontend to make tests pass.
- **Preserve now:** untracked `apps/web/app/dedup/`, `apps/web/lib/dedup.*`, and related dirty contract/nav/actions changes on this branch.

### Doc conflicts (prefer code when they disagree)

| Conflict | Prefer |
| --- | --- |
| API version: eng docs/OpenAPI **0.20.0** (this branch) vs README / some release docs **0.19.0** | Code + `apps/api/openapi.json` on the branch being shipped |
| E03: ENGINE_REGISTER / ROADMAP say bounded diligence exists; `TRACEABILITY.md` still says E03 not implemented | Code + `014_diligence_requests.sql` + diligence routes/tests |
| `VERIFICATION_REGISTER.md` (~2026-11-04 counts) vs BUILD_LEDGER later counts (250 / 273 / 161+118) | Re-run tests; treat register as historical unless refreshed |
| `PROJECT_STATUS.md` | **Does not exist.** Closest living snapshot: `docs/engineering/IMPLEMENTATION_STATUS.md` |

### Open PRs (at audit)

| PR | Title | Notes |
| --- | --- | --- |
| #42 | Dependabot Next 15.5.28 → 15.5.29 | Dependency bump |
| #40 | T-NEXT-009 PostGIS still blocked | Docs |
| #39 | Record PR #38 merge + OpenTelemetry CVE bump | Docs (stale relative to later merges) |

### Must not rebuild

- Property Identity private create/read/share + tenant isolation + unverified claims already on main (`AGENTS.md`).
- Closed E01 slices: attribution chain (PRs #25–#31), evidence graph/conflicts (PRs #33–#37), CSP/presentation (PR #38), membership session posture (PR #41), conflict dispositions (PR #43).
- Frozen `oydp/` + root `migrations/`.
- Automatic property merge, title verification, or fake scanner “pass.”

---

## 2. Engine-by-engine maturity matrix

Labels are evidence-constrained. Nothing in this repo qualifies as `production-hardened` or `independently reviewed`.

| ID | Engine | Maturity | Evidence pointers |
| --- | --- | --- | --- |
| **E01** | Property Identity & Evidence Graph | **executable implementation** + **integration-tested (partial)** | API: `apps/api/app/main.py` (`/v1/properties*`, claims, access, writers, corrections, documents, identifiers, sources, reviews, evidence-graph/conflicts/dispositions, consents, exports, audit, dedup-candidates on this branch). Auth: `apps/api/app/auth.py`. Docs: `apps/api/app/documents.py` (scanner always `None`, fail-closed). DB: `infra/db/001`–`022` (+ `023` untracked). Web: `/properties*`, `/evidence`, graph tab + dispositions, `/activity`, `/overview`; local `/dedup`. Tests: `apps/api/tests/*`, `tests/integration/test_*.py`. PRs: #25–#38, #41, #43; branch work for dedup. Register: `docs/ENGINE_REGISTER.md`. **Not** title, auto-merge, or complete graph. |
| **E02** | AI Property Advisor | **planned** | Disclosure only: `apps/web/app/engines/page.tsx`, ROADMAP M2 unchecked. No advisor API/DB. `/decision` is a thin **UI prototype** over E01 reads — not E02. |
| **E03** | Transaction & Legal Workspace | **executable implementation (bounded)**; diligence **integration-tested**; remainder **planned** | `infra/db/014_diligence_requests.sql`; API diligence open/note/close; web `/diligence` + property tab; `tests/integration/test_z_diligence.py`. Not offers, payments, or legal conclusions. |
| **E04** | Living Property Passport | **planned** | Consent purpose `passport_export` exists on E01 export path — naming hook only, not a passport product. ROADMAP M2 open. |
| **E05** | Ownership Action Engine | **planned** | Engines page + docs only. |
| **E06** | Real Estate Academy | **planned** | Engines page + docs only. |
| **E07** | SpatialLedger GIS Intelligence | **planned** | No GIS product routes in `apps/api`. PostGIS local acceptance (**T-NEXT-009**) is infra/IDOR work, not E07. |
| **E08** | Property Valuation & Market Intelligence | **planned** | Engines page + docs only. |
| **E09** | Layout & Architecture Concept Studio | **planned** | Engines page + docs only. |
| **E10** | Development & Business Feasibility | **planned** | Engines page + docs only. |
| **E11** | Marketplace & Professional Network | **planned** | Engines page + docs only. |
| **E12** | Time-Versioned Spatial Digital Twin | **planned** | Engines page + docs only. |
| **E13** | Institutional API & Evidence Attestations | **planned** | Private property API ≠ institutional attestations. |

**Shared foundation (not an engine):** OIDC/JWKS verification, tenant RLS (`app.tenant_id`), membership + session not-before (migration 021), MFA `amr` + `auth_time` freshness, process-local rate limit, CSP middleware, secret scan + pip-audit in CI. Live IdP enrollment and malware scanner remain **BLOCKED** / fail-closed.

---

## 3. Architecture & constraints

### Modular monolith

- One product: Next.js (`apps/web`) + FastAPI (`apps/api`) + PostgreSQL/PostGIS intent (`infra/db`).
- All 13 engines remain bounded launch commitments inside shared identity, authorization, evidence, and audit — **do not** split into 13 apps or silently drop engines.
- Deterministic code owns authz, money, policy, validation, and critical state. AI (when built) must be source-grounded and abstain on unknowns. Uploads are untrusted.

### Geography

Initial coverage: Bengaluru Urban, Bengaluru Rural, other Karnataka districts, Hyderabad. Respect coverage-specific regulatory and data limits. Do not claim government affiliation or official registry integration.

### Security non-negotiables

1. Server-side authorization on every protected operation; never trust client authz.
2. Tenant isolation via membership + RLS GUCs; cross-tenant IDOR negatives required.
3. OIDC RS256 `at+jwt` with configured JWKS; string subjects; MFA gates on high-risk writes.
4. Documents quarantine/encrypt; download denied until scan `pass` — **no fake scanner success**.
5. Audit append-only / outbox semantics; no silent user alteration of ledger.
6. Parameterized SQL; migration checksum discipline under `infra/db` only.
7. Secrets via env; never commit `.env`, tokens, or private property records.
8. No title verification, guaranteed valuation, or official attestation claims.

### Dual-backend trap (repeat)

Evolve **only** `apps/api` + `infra/db` + `apps/web`. Keep reference discovery separate. Green `checks.yml` ≠ ship gate for the active API.

---

## 4. Phased build plan

Phases are ordered. Later phases assume earlier acceptance unless explicitly parallelizable. Each ticket lists dependencies, acceptance, suggested tests (including negatives), and explicit **NOT**s.

### Phase 0 — Stabilize current baseline (immediate)

**Goal:** Land or safely park the in-flight dedup work; keep main honest; do not stall on Docker/PostGIS.

| Ticket | Work | Deps | Acceptance | Suggested tests | NOT |
| --- | --- | --- | --- | --- | --- |
| **P0-1** Finish/ship T-E01-DEDUP-1 | Commit only when asked; open PR for `feat/property-dedup-candidates`; CI green (`api-smoke`, `database-security`, `web`) | Local TESTED evidence in BUILD_LEDGER | Migration 023 applied via active migrator; generate/compare/review only; `properties_merged=false`; `title_effect=none`; MFA + RLS + IDOR | Static `test_migration_023_static.py`; unit MFA gates for dedup routes; integration generate/review + cross-tenant deny; web `dedup.test.mjs` + typecheck/build | Auto-merge; claim verification; clearing conflicts |
| **P0-2** Doc sync after merge | Align README API badge, RELEASE_READINESS version notes, TRACEABILITY E03 row, refresh VERIFICATION_REGISTER if counts change | P0-1 merge (or explicit defer) | Docs match shipped API version and engine reality | Doc review vs OpenAPI + ENGINE_REGISTER | Claiming GA |
| **P0-3** Close or refresh stale docs PRs | #39 / #40: merge if still accurate, or supersede with current ledger | Human decision | No contradictory “next task” docs | — | Force-push; rewriting history |
| **P0-4** Dependabot #42 | Review Next bump; run web CI | — | `npm test` / typecheck / build green | web.yml | Blind merge without CI |

**Phase 0 security/verification gates:** zero-skip JUnit on active DB CI; OpenAPI `--check`; `secret_scan_light.py` 0 hits; no weaken MFA/RLS; preserve untracked web if PR splits.

---

### Phase 1 — E01 depth (high value, still pre-alpha)

**Goal:** Deepen Property Identity & Evidence Graph without title or auto-merge. Prefer implementable work over blocked infra.

| Ticket | Work | Deps | Acceptance | Suggested tests | NOT |
| --- | --- | --- | --- | --- | --- |
| **P1-1** T-E01-GRAPH (incremental) | Extend read-only evidence graph beyond current identifiers/reviews/export (lineage edges still missing vs blueprint) | Dedup landed or explicitly deferred | Graph remains read-only; `title_verified` / title effect never true; RLS | Authz + cross-tenant graph deny; contract tests | Write-side “resolve” that verifies claims |
| **P1-2** Conflict UX depth | Stronger web surfacing of withdrawn citations + disposition history (no new outcome types without design) | PR #43 | Only `noted` / `kept_unresolved`; signals stay unresolved | Web unit + bounce error paths | Outcomes that clear conflicts or assert title |
| **P1-3** G-MFA-INT deepen | Add DB-backed MFA negative cases without overriding `require_mfa` on more high-risk paths | Existing route units | Integration proves MFA on selected write paths with real Depends | Extend `test_z_*` carefully | Disabling MFA in prod config |
| **P1-4** G-WEB-DEPTH | Wire remaining E01 read/write surfaces still API-only (as prioritized) | Session/CSP intact | Server actions via `lib/api.ts`; no `NEXT_PUBLIC_*` API origin; CSP holds | web unit + middleware/csp tests | Fake engine completeness on `/engines` |
| **P1-5** T-NEXT-009 (when unblocked) | PostGIS disposable env + spatial/IDOR acceptance | Docker/PostGIS available | Native PostGIS suite green; document active CI strategy | IDOR + RLS under PostGIS | Stalling all E01 work until Docker returns |

**Phase 1 gates:** active unit + integration 0 skip in CI; negative cross-tenant on every new table/RPC; migration static privilege tests for new SECURITY DEFINER helpers; web build/typecheck; threat-model row updates if attack surface changes.

---

### Phase 2 — Security & foundation (parallel with Phase 1 where possible)

**Goal:** Close implementable security gaps; document remaining external blockers honestly.

| Ticket | Work | Deps | Acceptance | Suggested tests | NOT |
| --- | --- | --- | --- | --- | --- |
| **P2-1** T-SEC-006 / G-IDP | Live Keycloak (or chosen IdP) enrollment; verify `amr` + `auth_time`; document provider revocation | Docker/IdP ops | Live script evidence; no prod bypass flags | Live token negatives; revoked membership + provider revoke if available | Claiming SF-006 closed on DevOidc alone |
| **P2-2** T-SEC-003 / G-SCAN | Real malware scanner adapter behind existing quarantine gate | Approved scanner product/budget | Fail-closed until `pass`; no silent skip | Upload → quarantine → deny content → pass → allow | Bundling a fake “always pass” scanner |
| **P2-3** G-RATELIMIT | Distributed/edge-aware throttle design (or explicit ops control) | Architecture decision | Document limits; multi-worker behavior known | Abuse tests at chosen layer | Claiming DDoS immunity from process-local dict |
| **P2-4** G-WORM | External immutable audit sink from outbox | Ops | Delivered events retained immutably; app users cannot alter | Outbox deliver + tenant isolation | Calling in-DB ledger “WORM” |
| **P2-5** G-PRIVACY | Deletion, retention, legal hold, restore drills | Legal/product design | Spec + tested workflows | Negative restore/authz | Shipping without policy |
| **P2-6** G-REVIEW | Named independent security/human review | Human reviewers | Written findings + remediations tracked | — | Self-declaring “independently reviewed” |

**Phase 2 gates:** SF findings updated in `SECURITY_STATUS.md` / `SECURITY_FINDINGS.md` with evidence; no production claim until external items close or are explicitly accepted as residual risk.

---

### Phase 3 — Collaborative lifecycle (Milestone 2)

**Goal:** First non-E01 engines as **real** bounded slices — never placeholders labeled complete.

| Ticket | Engine | Suggested first vertical slice | Deps | Acceptance | NOT |
| --- | --- | --- | --- | --- | --- |
| **P3-1** | E03 expand | After diligence: designed transaction checklist / document request templates still non-legal, non-payment | E01 stable | Deterministic state machine; MFA on mutations; RLS | Offers/payments/legal conclusions without counsel |
| **P3-2** | E04 | Living passport view = versioned export package of consented evidence (reuse `passport_export`) | E01 consents/export | Consent-gated; abstain on missing rights | “Official passport” branding |
| **P3-3** | E05 | Ownership action inbox: proposed actions as unverified requests with audit | E01 grants | No silent ownership change | Auto-executing title changes |
| **P3-4** | E02 | Source-grounded Q&A over **cited** E01 evidence only; abstain on unknowns | E01 graph/export | Citations required; no invented registry facts | Scraping government portals |
| **P3-5** | E06 | Curriculum/content shell with authz; no fake certification | Shared auth | Honest “academy content” labeling | Claiming licensed education authority |

**Phase 3 gates:** per-engine OpenAPI + migration + negative auth/tenant tests + ENGINE_REGISTER update; `/engines` page stays honest.

---

### Phase 4 — Spatial & financial decision support (Milestone 3)

| Ticket | Engine | First slice | Hard constraints |
| --- | --- | --- | --- |
| **P4-1** | E07 | Parcel/layer read with CRS + source attribution inside tenant | Requires PostGIS; no unofficial survey scrape |
| **P4-2** | E08 | Licensed comparable research notes (advisory) | Never guarantee returns/value |
| **P4-3** | E09 | Concept layout sandbox, non-approved designs | Explicit non-approval disclaimer |
| **P4-4** | E10 | Reproducible feasibility calculator with fixed inputs/outputs | Deterministic; no hidden AI money math |
| **P4-5** | E12 | Time-versioned spatial snapshot on top of E07 | Depends on E07 data model |

**Phase 4 gates:** geography coverage limits enforced; AI/GIS/financial verification tests; no government API claims.

---

### Phase 5 — Network, institutions, GA (Milestones 4–5)

| Ticket | Work | Notes |
| --- | --- | --- |
| **P5-1** E11 | Consent-based marketplace + moderation | Least privilege; abuse reporting |
| **P5-2** E13 | Institutional API: scoped grants, revocation, attestations of **OYDP-held evidence** only | Not government attestation |
| **P5-3** GA gates | External security review; privacy/deletion; 13 real e2e journeys; restore drills; SLOs; signed product/eng/security/legal decision | Per ROADMAP Milestone 5 — **none are done** |

**Phase 5 NOT:** public deploy, paid pilot, or “production-ready” badges without signed gates.

---

## 5. Near-term recommended next increments

Smallest high-value vertical slices **after** current baseline (ordered):

1. **Ship T-E01-DEDUP-1** — commit/PR/CI/merge when you ask; keep non-merge invariants; preserve `/dedup` web.
2. **Doc honesty pass** — README API badge, TRACEABILITY E03, verification register refresh (P0-2).
3. **E01 graph depth (P1-1)** — next evidence-graph edges still missing vs blueprint; read-only.
4. **G-MFA-INT / web depth (P1-3 / P1-4)** — strengthen negatives and remaining E01 UI gaps without new engines.
5. **When Docker returns:** T-NEXT-009 PostGIS acceptance — do **not** block 1–4 on it.
6. **When IdP/scanner budget exists:** T-SEC-006 then T-SEC-003 — before any public demo beyond private loopback.
7. **First new engine slice:** E04 passport export packaging **or** designed E03 expansion — only after E01 dedup is on main and security blockers are consciously accepted for private pre-alpha.

Skip: rebuilding Property Identity; automatic merge; rewriting `oydp/`; stalling on T-NEXT-009; labeling E02–E13 anything but planned until code exists.

---

## 6. Security & verification gates (per phase)

Aligned with `oydp-master.mdc`:

| Gate | Phase 0–1 | Phase 2 | Phase 3–4 | Phase 5 |
| --- | --- | --- | --- | --- |
| Implement real behavior (no mock success) | Required | Required | Required | Required |
| Authn fail-closed / MFA on high-risk writes | Required | Live IdP verification | Per-engine | Org-wide |
| Tenant RLS + IDOR negatives | Required on every new surface | + provider revoke | Required | Required |
| Migration under `infra/db` + privilege static tests | Required | Required | Required | Required |
| Active CI: `api-smoke` + `database-security` (0 skip) | Required | Required | Required | Required |
| `web.yml` when FE touched | Required | As needed | Required | Required |
| Secret scan + dependency audit | Required | Required | Required | Required |
| OpenAPI check | Required | Required | Required | Required |
| External WORM / scanner / privacy | Document residual | Close or accept | — | Must close for GA |
| Independent review | Not claimed | Schedule | — | Required for GA |
| Reference `checks.yml` | Optional regression only | Optional | Optional | Optional — never sole gate |

**Test commands (active):**

```text
PYTHONPATH=apps/api:. python -m pytest apps/api/tests tests/integration
python scripts/export_active_openapi.py --check
python scripts/secret_scan_light.py
# apps/web:
npm test && npm run typecheck && npm run build
```

**Reference (separate):**

```text
PYTHONPATH=. python -m pytest tests/test_api.py tests/test_database.py tests/test_foundation.py
```

Passing tests mean those commands were executed and passed. Historical BUILD_LEDGER counts are not a substitute for a fresh run on the commit you ship.

---

## 7. Risks / open questions / preserve-list

### Critical blockers / risks

| ID | Risk | Impact |
| --- | --- | --- |
| Dirty dedup tree | API 0.20.0 + 023 + web `/dedup` uncommitted — easy to lose or collide with other worktrees | High |
| G-IDP / SF-006 | No live IdP enrollment / provider revocation proof | High for any shared demo |
| G-SCAN / SF-003 | No malware scanner | Medium; mitigated fail-closed |
| T-NEXT-009 | PostGIS IDOR acceptance blocked (no Docker) | Medium; active CI uses `postgres:16` only |
| G-REVIEW | No independent security review | High for any “hardened” claim |
| G-PRIVACY | No deletion/retention/restore | High before multi-tenant production |
| G-RATELIMIT | Process-local only | Medium under multi-worker |
| Dual-backend confusion | Contributors may “fix” wrong tree or cite wrong CI | High process risk |
| Doc skew | README/TRACEABILITY/VERIFICATION_REGISTER lag eng ledgers | Medium trust risk |
| Local main checkout lag | Local `main` ref may sit behind `origin/main` on some machines/worktrees | Process hazard |

### Open questions

1. Merge order: dedup PR first vs Dependabot #42 / docs #39–#40?
2. When Docker returns, does active `database-security.yml` stay on `postgres:16` with a separate PostGIS job, or switch?
3. Which IdP is canonical for first live enrollment (Keycloak vs other)?
4. First post-E01 engine priority: E04 passport packaging vs E03 expansion vs E02 grounded advisor?
5. Who performs G-REVIEW, and against which threat model revision?

### Preserve-list (do not overwrite / discard)

- Untracked / dirty `apps/web` work on this branch (`app/dedup/`, `lib/dedup.*`, related contract/nav/actions).
- PR #5 lineage and CSP/session/server-action patterns.
- Applied SQL migration checksums; add only under `infra/db`.
- Frozen `oydp/` + root `migrations/`.
- Parallel worktrees/branches listed in local git (membership, security, docs close-outs, etc.).
- Explicit non-merge / non-title invariants in dispositions and dedup.

---

## 8. Definition of done

### For this plan document

Done when:

- [x] Session inventory completed (git, docs, both backends, web, engines, auth/RLS, tests/CI).
- [x] Plan written to `docs/engineering/BUILD_PLAN.md`.
- [x] Maturity labels are evidence-backed; conflicts noted.
- [x] Phases include tickets, deps, acceptance, tests, and NOT lists.
- [x] Preserve-list and blockers are explicit.
- [ ] *(Optional follow-up)* Human acknowledges plan; links it from `docs/README.md` / IMPLEMENTATION_STATUS “next eligible.”

This plan is **not** done as “execution complete” — it is a steering artifact.

### For each phase

A phase is done only when:

1. Scoped tickets are **real** functionality in `apps/api` / `infra/db` / `apps/web` as applicable.
2. Existing behavior and preserve-list items remain intact.
3. Applicable security controls from §6 are implemented and verified.
4. Relevant tests were **executed** and passed (or blockers documented with strongest alternative).
5. Typecheck/lint/build (and OpenAPI/secret scan where applicable) succeed.
6. Diff reviewed; docs match implementation; no critical/high issue introduced left open without documentation.
7. If delivery was requested: feature branch committed/pushed and remote SHA verified — **without** merging to `main` unless separately approved.
8. Maturity labels in ENGINE_REGISTER / engineering status updated honestly — never to `production-hardened` or `independently reviewed` without external evidence.

---

## Appendix A — Inventory quick reference

| Area | Path |
| --- | --- |
| Active API | `apps/api/app/{main,auth,documents,pagination,rate_limit}.py` |
| Active OpenAPI | `apps/api/openapi.json` |
| Active migrations | `infra/db/001_*.sql` … `022_*.sql` (+ `023_*` on dedup branch) |
| Reference API | `oydp/` |
| Reference migrations | `migrations/` |
| Web app | `apps/web/app/**` |
| Active unit tests | `apps/api/tests/` |
| Active integration | `tests/integration/` |
| CI | `.github/workflows/{api-smoke,database-security,web,checks}.yml` |
| Engine register | `docs/ENGINE_REGISTER.md` |
| Living status | `docs/engineering/{IMPLEMENTATION_STATUS,BUILD_LEDGER,KNOWN_GAPS,SPRINT_STATUS}.md` |
| Threat model | `docs/THREAT_MODEL.md` |

## Appendix B — Recent mainline product merges (context)

| PR | Topic |
| --- | --- |
| #43 / #44 | Evidence conflict dispositions + ledger close / next dedup task |
| #41 | Membership session posture (no live IdP) |
| #38 | CSP middleware + repo presentation + attribution UI follow-ups |
| #37 | Web evidence graph / conflicts wiring |
| #35 / #33 | Conflict signals; read-only evidence graph |
| #31–#25 | Review/document/claim attribution chain |

---

*End of build plan. Re-audit git status before executing tickets — this workspace was dirty for dedup at audit time.*
