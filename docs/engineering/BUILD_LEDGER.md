# Build ledger

Append-only style session ledger for autonomous execution. Newest entry first.

## 2026-11-26 — Evidence conflict disposition (non-title)

### Completed

1. Continued on worktree `feat/evidence-conflict-disposition` from `origin/main` @ `32b348a` (PR #41 merged). Preserved main checkout, stash, and parallel worktrees (`feat/evidence-conflict-adjudication`, docs/security trees). Untracked temps in the main checkout were not discarded.
2. Migration **022** adds append-only `evidence_conflict_dispositions` for `identifier_conflict` and withdrawn citation signals. Outcomes are only `noted` / `kept_unresolved`. No claim verification change, no identifier conflict clear, no property merge, `title_effect=none`.
3. API **0.19.0**: MFA-gated `POST /v1/properties/{id}/evidence-conflict-dispositions`; paginated GET; `GET .../evidence-conflicts` includes disposition annotations; audit event `conflict.disposition_recorded`.
4. Portable PostgreSQL 16.15 @ `127.0.0.1:55432`, fresh DB `oydp_disposition_test`.
   - Combined active suite → **273 passed**, 0 failed, 0 skipped, 1 Starlette deprecation warning.
   - `export_active_openapi.py --check` → match. `secret_scan_light.py` → `SECRET_SCAN_HITS 0`.
   - Web UI for dispositions not wired this slice (API + contract only).
5. **T-NEXT-009** PostGIS remains BLOCKED. Live IdP / scanner / GA unchanged.

### Next task (resume here)

Open a PR for this branch when asked. Then unblocked E01 depth: property dedup candidates, disposition web display, or G-WEB-DEPTH. Skip T-NEXT-009 while Docker is unavailable. Not GA.

---

## 2026-11-17 — Membership-revoke session posture (no live IdP)

### Completed

1. Branched `feat/membership-session-posture` from `origin/main` @ `d960308` (PR #38 merged). Open PRs #39 and #40 were left unmerged. Local scratch files and the existing stash were not discarded.
2. Migration **021** records append-only membership session invalidations. Owner revoke deletes the membership (read/write grants cascade) and sets `not_before` to `floor(epoch)+1`. A tenant advisory lock stops two owners from revoking each other down to zero owners. Session kill invalidates tokens without removing membership.
3. API **0.18.0**: `POST /v1/tenant/membership-revocations` and `POST /v1/tenant/session-invalidations` are owner-only and MFA-gated. Every authorized request fails closed without a current membership, then rejects `iat < not_before`. No live IdP call.
4. Portable PostgreSQL 16.15 @ `127.0.0.1:55432`, fresh DB `oydp_membership_session_test`.
   - `PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests` → **152 passed**, 0 failed, 0 skipped, 1 Starlette deprecation warning.
   - `TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/oydp_membership_session_test` + `PYTHONPATH=apps/api;. python -m pytest -q tests/integration` → **116 passed**, 0 failed, 0 skipped, 1 warning.
   - `python scripts/export_active_openapi.py --check` → Active OpenAPI contract matches.
   - `python scripts/secret_scan_light.py` → `SECRET_SCAN_HITS 0`.
   - Web not modified for behavior; npm test/typecheck/build not run.
5. **T-NEXT-009** PostGIS remains BLOCKED. Live IdP enrollment and provider token revocation remain BLOCKED (SF-006). Not GA.

### Next task (resume here)

Do not merge this PR unless CI is green and a human asks. Then unblocked E01 depth (skip T-NEXT-009): adjudication/dedup or G-WEB-DEPTH. Not GA.

---

## 2026-11-12 — PR #38 PG acceptance + merge gate

### Completed

1. Verified live state: `origin/main` @ `f350a99` (PR #37 T-NEXT-011 merged). Open PR #38 CI green / MERGEABLE. Working tree clean on `security/web-csp-and-repo-presentation`.
2. Portable PostgreSQL 16.15 on `127.0.0.1:55432` (trust); recreated `oydp_security_test`.
3. `TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/oydp_security_test` + `PYTHONPATH=apps/api;.` → `pytest -q apps/api/tests tests/integration` → **250 passed**, 0 skipped, 0 failed (covers migration 020 + attribution negatives).
4. `scripts/check_test_report.py` → Acceptance report verified: 250 cases; zero skips/failures. OpenAPI `--check` match. `SECRET_SCAN_HITS 0`.
5. **T-NEXT-011** closed on main via PR #37 — do not redo. **T-NEXT-009** remains BLOCKED (no Docker/PostGIS).

### Next task (resume here)

Merge PR #38 when CI remains green. Then unblocked security/foundation/E01 depth (skip T-NEXT-009): prefer membership-revoke session posture without live IdP where possible, then E01 adjudication/dedup or G-WEB-DEPTH. Not GA.

---

## 2026-11-12 — PR #38 batch: OpenAPI, T-NEXT-012, conflicts, throttle, docs posture

### Completed

1. Regenerated `apps/api/openapi.json` via `scripts/export_active_openapi.py`; `--check` PASS (AUD-001).
2. **T-NEXT-012:** web claim optional source citation; review claim/document/identifier citations; document attribution PUT UI + display; notices for success/error via existing bounce path.
3. Evidence conflicts include `documents_citing_withdrawn_sources` and `reviews_citing_withdrawn_sources` (API **0.17.0**).
4. Process-local mutation rate limit (`app/rate_limit.py`); interactive `/docs` off unless `OYDP_OIDC_DEV_HTTP=1` or `OYDP_ENABLE_API_DOCS=1`.
5. Static migration-020 privilege assertions; orphan web clients documented in `apps/web/lib/LEGACY_CLIENTS.md` (kept for unit tests).
6. Earlier unit-only verification: API **140 passed**; web **48 passed**; typecheck/build OK; `secret_scan_light.py` **0 hits**. PG integration completed in newer ledger entry (250 passed).

### Next task (resume here)

See newer ledger entry (PG acceptance + merge).

---

## 2026-11-12 — CSP middleware + audit forge / source-gate follow-up

### Completed

1. Branched `security/web-csp-and-repo-presentation` from `origin/main`.
2. Wired Next.js 15 CSP entry as `apps/web/middleware.js` (previous `proxy.js` was not loaded by the framework; middleware-manifest was empty).
3. Root layout uses `connection()` for a request boundary; removed React inline `style={{...}}` so `style-src 'self'` can enforce.
4. Aligned README / CONTRIBUTING / SECURITY / docs index; added `docs/README.md` and proprietary `LICENSE`.
5. Follow-up from API audit: migration **020** closes direct `property_audit_events` INSERT (SECURITY DEFINER helpers), freezes `evidence_assertions` DML, restricts source withdrawal to creator/owner, merges document attribution fields, aligns diligence open/close with creator gate. API **0.16.0** (superseded by 0.17.0 in later entry).
6. Web hygiene: `apps/web/README.md`, decision bucket label, e2e Continue selectors.

---

## 2026-11-12 — T-NEXT-011 web evidence graph / conflicts wiring

### Completed so far

1. Branched `feat/web-evidence-graph-wiring` from `main` @ `1501d46`.
2. `apps/web` property tab **Evidence graph** loads `GET .../evidence-graph` and `GET .../evidence-conflicts` via existing session API client (server-side only).
3. UI shows empty/error/permission messages, unresolved-signal disclaimers, and attribution edges; no client-side authz.
4. Web verification: `npm test` **44 passed**; `npm run typecheck` OK; `npm run build` OK. Backend not modified.

### Next task (resume here)

After this PR merges: next unblocked E01 depth (skip T-NEXT-009). Prefer remaining G-WEB-DEPTH or foundation negatives without Docker. Not GA.

**Human blockers:** Docker/Keycloak (blocks T-NEXT-009); live IdP; malware scanner; independent review.

---

## 2026-11-12 — T-NEXT-010 evidence conflict signals + export sources

### Completed

1. Marked **T-NEXT-009** PostGIS IDOR as **BLOCKED** (Docker engine unavailable) in BUILD_LEDGER / KNOWN_GAPS; do not stall the project.
2. Branched `feat/evidence-conflict-signals` from `main` @ `ecceab5`.
3. API **0.15.0**: `GET .../evidence-conflicts` surfaces unresolved multi-claim / identifier-conflict / withdrawn-source citation signals without adjudication; export packets include cited `sources`.
4. Disposable PG `127.0.0.1:55432` suite: **244 passed, 0 skipped**; JUnit guard OK; OpenAPI `--check` match; `SECRET_SCAN_HITS 0`.
5. PR [#35](https://github.com/Manasvi-1/OYDP/pull/35) **merged** to `main` @ `0199033` via `gh pr merge --merge`.
6. PR [#36](https://github.com/Manasvi-1/OYDP/pull/36) ledger close **merged** @ `1501d46`.

### Next task (resume here)

**T-NEXT-011:** see newer ledger entry. **T-NEXT-009 remains BLOCKED.**

---

## 2026-11-12 — T-NEXT-008 read-only evidence-graph projection

### Completed

1. Branched `feat/evidence-graph-projection` from `main` @ `659a130`.
2. API **0.14.0** `GET /v1/properties/{id}/evidence-graph` — read-only edge projection from existing claim/document/review attribution columns under `readable_property` + tenant RLS; `title_verified` false; no MFA (matches other property list reads); no new migration.
3. Contract + integration + IDOR coverage for empty/happy/cross-tenant/unauthorized paths.
4. Disposable PG `127.0.0.1:55432` suite: **242 passed, 0 skipped**; JUnit guard OK; OpenAPI `--check` match; `SECRET_SCAN_HITS 0`.
5. PR [#33](https://github.com/Manasvi-1/OYDP/pull/33) **merged** to `main` @ `5e63072` via `gh pr merge --merge`.
6. PR [#34](https://github.com/Manasvi-1/OYDP/pull/34) ledger close **merged** @ `ecceab5`.

### Next task (resume here)

**T-NEXT-009 BLOCKED** (no Docker/PostGIS). Continue unblocked E01 work — see T-NEXT-010 entry.

---

## 2026-11-12 — T-NEXT-007 review↔document/identifier attribution

### Completed

1. PR [#30](https://github.com/Manasvi-1/OYDP/pull/30) **merged** to `main` @ `60e249e` via `gh pr merge --merge`.
2. Branched `feat/review-document-identifier-attribution` from that tip.
3. `infra/db/019_review_document_identifier_attribution.sql` — optional `document_id` / `identifier_id` on reviews; eight-arg `record_professional_review`; same-property document + current identifier only; `title_effect` stays none.
4. API **0.13.0** surfaces those citation fields on create/list/export.
5. Disposable PG `127.0.0.1:55432` suite: **240 passed, 0 skipped**; JUnit guard OK; OpenAPI `--check` match; `SECRET_SCAN_HITS 0`.
6. PR [#31](https://github.com/Manasvi-1/OYDP/pull/31) **merged** to `main` @ `55312ef` via `gh pr merge --merge`.
7. PR [#32](https://github.com/Manasvi-1/OYDP/pull/32) ledger close **merged** @ `659a130`.

### Next task (resume here)

**T-NEXT-008:** see newer ledger entry.

---

## 2026-11-12 — T-NEXT-006 review↔claim attribution

### Completed

1. PR [#28](https://github.com/Manasvi-1/OYDP/pull/28) **merged** to `main` @ `116bde9` via `gh pr merge --merge` (no smart-mode card).
2. Branched `feat/review-claim-attribution` from that tip.
3. `infra/db/018_review_claim_attribution.sql` — optional `claim_id` on `professional_reviews`; six-arg `record_professional_review`; unverified same-property claims only; `title_effect` stays none.
4. API **0.12.0**; reviews/list/export carry optional `claim_id`.
5. Disposable PG `127.0.0.1:55432` suite: **240 passed, 0 skipped**; JUnit guard OK; OpenAPI `--check` match; `SECRET_SCAN_HITS 0`.
6. PR [#29](https://github.com/Manasvi-1/OYDP/pull/29) **merged** to `main` @ `c432b0d` via `gh pr merge --merge`.
7. PR [#30](https://github.com/Manasvi-1/OYDP/pull/30) ledger close **merged** @ `60e249e`.

### Next task (resume here)

**T-NEXT-007:** see newer ledger entry.

---

## 2026-11-12 — T-NEXT-005 document↔identifier + export refs

### Completed

1. PR [#27](https://github.com/Manasvi-1/OYDP/pull/27) **merged** to `main` @ `82df32e` (merge commit strategy matching #22–#26). Local `origin/main` synced.
2. Branched `feat/document-identifier-attribution` from that tip.
3. `infra/db/017_document_identifier_attribution.sql` — optional `identifier_id` FK; six-arg `attribute_property_document`; current identifiers only.
4. API **0.11.0**; attribution + export packet document metadata carry `claim_id` / `source_id` / `identifier_id`; `title_verified` remains false.
5. Disposable PG `127.0.0.1:55432` suite: **240 passed, 0 skipped, 0 failed**; JUnit guard `tests=240 failures=0 errors=0 skipped=0`; OpenAPI `--check` match; `SECRET_SCAN_HITS 0`; IDOR file 8 collected.
6. PR [#28](https://github.com/Manasvi-1/OYDP/pull/28) **merged** to `main` @ `116bde9`.

### Next task (resume here)

**T-NEXT-006:** review↔claim — see newer ledger entry.

---

## 2026-11-11 — T-NEXT-004 document attribution

### Completed

1. `infra/db/016_document_attribution.sql` + `attribute_property_document` — optional `claim_id` / `source_id` on `property_documents`.
2. `PUT .../documents/{id}/attribution` (MFA); withdrawn/foreign/empty denied; runtime cannot UPDATE links directly; scan_state unchanged; claims stay unverified.
3. API **0.10.0**; IDOR probe for attribution; local disposable PG suite **240 passed, 0 skipped**.
4. PR [#27](https://github.com/Manasvi-1/OYDP/pull/27) opened @ `efc8d2e`; CI green; later **merged** to `main` @ `82df32e` (earlier smart-mode approval card failure was transient).

### Next task (resume here)

**T-NEXT-005:** document↔identifier + export attribution refs — see newer ledger entry.

---

## 2026-11-11 — T-NEXT-001 local PG + claim→source graph edge

### Completed

1. **T-NEXT-001:** Disposable PostgreSQL 16.15 portable cluster on `127.0.0.1:55432` (trust auth). Docker CLI absent; Docker Desktop present but engine pipe unavailable; system PG 17 on 5432 lacks known password / unused. Active API needs `pgcrypto` only (not PostGIS) — matches CI `postgres:16`.
2. Fresh DB `oydp_security_test` + full suite: **238 passed, 0 skipped, 0 failed**; JUnit guard verified; IDOR file **8/8 passed**.
3. **T-E01-GRAPH slice:** `infra/db/015_claim_source_attribution.sql` — optional live `source_id` on claims via `record_property_claim`; withdrawn/foreign sources rejected; claims stay `user_claim`/`unverified`; API 0.9.0; secret scan wired into Active API smoke.

4. PR #25 merged to `main` @ `7f218c3` after full CI SUCCESS.
5. PR #26 ledger close merged @ `71553d2`.

---

## 2026-11-11 — Document route MFA negatives (follow-on)

### Completed

1. PR #22 merged to `main` @ `328edc6` after full CI SUCCESS (API smoke, DB security, web, reference).
2. Branched `security/document-route-mfa-gates` from `origin/main`.
3. Added `apps/api/tests/test_document_route_mfa_gates.py` for upload/scan/content MFA negatives (no scanner pass forgery).
4. PR #23 merged to `main` @ `6c56778` after full CI SUCCESS (131 unit tests in Active API smoke path).
5. PR #24 build-ledger close merged @ `5685dc1`.

---

## 2026-11-11 — Master autonomous execution (this session)

### Completed

1. Audited GitHub + local tree; classified A–G; confirmed PR #4/#5 MERGED historical; PR #22 OPEN CI green.
2. Detected feature-branch regression vs main (missing SF-008 + IDOR suite); merged `origin/main` → `ed7b5b7` (clean).
3. Added `apps/api/tests/test_mfa_route_gates.py` (real `require_mfa`, stub `authorized_db` only).
4. Corrected stale threat-model file-service row.
5. Created `docs/engineering/*` ledger set.
6. Delivered and **merged** PR #22 (`328edc6`).

### Verification this session

| Command | Result |
| --- | --- |
| `PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests` | **126 passed**, 0 failed, 1 Starlette deprecation warning |
| `PYTHONPATH=. python -m pytest -q tests/test_api.py tests/test_database.py tests/test_foundation.py` | **50 passed**, **37 skipped**, 13 subtests passed (skips = no native PostGIS env) |
| `python scripts/export_active_openapi.py --check` | Active OpenAPI contract matches |
| `python scripts/secret_scan_light.py` | `SECRET_SCAN_HITS 0` |
| Active integration `tests/integration` + IDOR | **NOT RUN** — `TEST_DATABASE_URL` unset, Docker absent |

### Git intent (delivery)

- Branch: `feat/interview-demo-workspace`
- Push merge + MFA route tests + engineering docs; update PR #22
- Merge PR #22 only if still green and eligibility holds (no branch protection; still require CI green + no critical defects)

4. PR #25 merged to `main` @ `7f218c3` after full CI SUCCESS.

### Next task (resume here)

**T-NEXT-001 (P0 when infra available):** Provision disposable PostGIS, set `TEST_DATABASE_URL`, run  
`PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests tests/integration`  
and record pass counts including `test_z_cross_tenant_idor.py`. Do not weaken skips.

**T-NEXT-002 (P1 if PG still blocked):** Expand document upload/content/export negative unit tests that exercise real authz dependencies without faking scanner `pass`, and/or wire `secret_scan_light` into Active API smoke if not already.

**T-NEXT-003 (P2):** E01 evidence-graph increment only after security local/CI gates remain green — no engine placeholder PRs.

### Resume state

- Working tree at end of implementation: docs + MFA tests + threat model + merge commit pending commit/push as one delivery.
- Do not force-push. Do not deploy. Preserve any future untracked `apps/web` user work.
