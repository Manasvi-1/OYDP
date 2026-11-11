# Build ledger

Append-only style session ledger for autonomous execution. Newest entry first.

## 2026-11-11 — T-NEXT-001 local PG + claim→source graph edge

### Completed

1. **T-NEXT-001:** Disposable PostgreSQL 16.15 portable cluster on `127.0.0.1:55432` (trust auth). Docker CLI absent; Docker Desktop present but engine pipe unavailable; system PG 17 on 5432 lacks known password / unused. Active API needs `pgcrypto` only (not PostGIS) — matches CI `postgres:16`.
2. Fresh DB `oydp_security_test` + full suite: **238 passed, 0 skipped, 0 failed**; JUnit guard verified; IDOR file **8/8 passed**.
3. **T-E01-GRAPH slice:** `infra/db/015_claim_source_attribution.sql` — optional live `source_id` on claims via `record_property_claim`; withdrawn/foreign sources rejected; claims stay `user_claim`/`unverified`; API 0.9.0; secret scan wired into Active API smoke.

4. PR #25 merged to `main` @ `7f218c3` after full CI SUCCESS.

### Next task (resume here)

**T-NEXT-004:** Document↔claim or document↔source attribution edge (new migration under `infra/db` only), or deepen export packet source disclosure — keep E01 Partial; no title claims.

**Human blockers:** Docker engine for compose Keycloak; live IdP enrollment; production malware scanner; independent review.

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
