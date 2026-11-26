# Test evidence

Only executed results are recorded. Skipped suites are named. Passing tests are not production approval.

## 2026-11-26 — Disposition web UI

Branch: `feat/evidence-conflict-disposition` (PR #43) continuing from API tip `c8690df`. Working directory `apps/web` after `npm ci`.

```text
npm test
npm run typecheck
npm run build
```

**Result:** `npm test` → **52 passed**, 0 failed, 0 skipped. `npm run typecheck` → exit 0. `npm run build` → exit 0 (Next.js 15.5.28). API/DB pytest not re-run (no API/DB change in this web slice). PostGIS / live IdP not run.

## 2026-11-26 — Evidence conflict disposition (migration 022)

Branch: `feat/evidence-conflict-disposition` from `origin/main` @ `32b348a`. System Python 3.11 with `sys.path` insert for `apps/api` (this interpreter's `python311._pth` ignores `PYTHONPATH`). Portable PostgreSQL **16.15** @ `127.0.0.1:55432`. Fresh database `oydp_disposition_test`. Docker not used. Web not modified.

```text
python -c "...pytest.main(['-q','apps/api/tests','tests/integration'])"
# with TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/oydp_disposition_test
python scripts/export_active_openapi.py --check
python scripts/secret_scan_light.py
```

**Result:** Combined active suite **273 passed**, 0 failed, 0 skipped, 1 Starlette/`httpx` deprecation warning. OpenAPI contract matches. `SECRET_SCAN_HITS 0`. npm test/typecheck/build not run. PostGIS / T-NEXT-009 not run. Live IdP not run.

## 2026-11-17 — Membership session posture (migration 021)

Branch: `feat/membership-session-posture` from `origin/main` @ `d960308`. Interpreter: repo `.venv` (system `python` is isolated by `python311._pth` and ignores `PYTHONPATH`). Portable PostgreSQL **16.15** @ `127.0.0.1:55432`. Fresh database `oydp_membership_session_test`. Docker not used. Web not modified.

```text
PYTHONPATH=apps/api;. .\.venv\Scripts\python.exe -m pytest -q apps/api/tests
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/oydp_membership_session_test
PYTHONPATH=apps/api;. .\.venv\Scripts\python.exe -m pytest -q tests/integration
.\.venv\Scripts\python.exe scripts/export_active_openapi.py --check
.\.venv\Scripts\python.exe scripts/secret_scan_light.py
```

**Result:** API units **152 passed**, 0 failed, 0 skipped, 1 Starlette/`httpx` deprecation warning. Integration **116 passed**, 0 failed, 0 skipped, 1 warning. OpenAPI contract matches. `SECRET_SCAN_HITS 0`. npm test, typecheck, and web build were not run. PostGIS / T-NEXT-009 not run. Live IdP not run.

## 2026-11-12 — PR #38 portable PG acceptance (migration 020)

Branch: `security/web-csp-and-repo-presentation` @ `d91c12a` (+ ledger update). Portable PG 16.15 @ `127.0.0.1:55432`, DB `oydp_security_test` recreated. Docker CLI absent.

```text
TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/oydp_security_test
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests tests/integration --junitxml=test-results/database-local.xml
python scripts/check_test_report.py test-results/database-local.xml
python scripts/export_active_openapi.py --check
python scripts/secret_scan_light.py
```

**Result:** **250 passed**, 0 skipped, 0 failed; guard verified; OpenAPI matches; `SECRET_SCAN_HITS 0`. PostGIS / T-NEXT-009 still blocked.

## 2026-11-11 — T-NEXT-004 document attribution

Branch: `feat/document-attribution`. Portable PG 16.15 @ `127.0.0.1:55432`, DB `oydp_security_test` recreated.

```text
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests tests/integration --junitxml=test-results/database-local.xml
python scripts/check_test_report.py test-results/database-local.xml
```

**Result:** **240 passed**, 0 skipped, 0 failed; guard verified; OpenAPI matches; secret scan 0 hits.

## 2026-11-11 — T-NEXT-001 local disposable PostgreSQL (portable 16.15)

**Environment:** Portable PostgreSQL 16.15 at `%LOCALAPPDATA%\Temp\oydp-pg` listening on `127.0.0.1:55432` (trust). Database `oydp_security_test` dropped/recreated before each full run. Docker CLI not on PATH; Docker Desktop engine pipe unavailable. System PostgreSQL 17 on 5432 not used (password unknown). Active migrations use `pgcrypto` only — PostGIS not required for this suite (same as CI `postgres:16`).

```text
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests tests/integration --junitxml=test-results/database-local.xml
python scripts/check_test_report.py test-results/database-local.xml
```

**Baseline on main `5685dc1`:** 238 passed, 0 skipped, 0 failed; guard verified.  
**IDOR only:** `tests/integration/test_z_cross_tenant_idor.py` → 8 passed.  
**After claim→source (`feat/claim-source-attribution`):** 238 passed, 0 skipped, 0 failed; guard verified; OpenAPI check matches; `secret_scan_light` → 0 hits.

## 2026-11-11 — Document route MFA follow-on

Branch: `security/document-route-mfa-gates` @ post-`328edc6`.

```text
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests
```

**Result:** 131 passed, 0 failed, 0 skipped (adds `test_document_route_mfa_gates.py`, 5 cases).

## 2026-11-11 — This session (Windows workstation)

Environment: Python `.venv`, `PYTHONPATH` with `;` separators (`apps/api` + repo root). No Docker. `TEST_DATABASE_URL` unset.

### Active API unit suite

```text
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests
```

**Result:** 126 passed, 0 failed, 0 skipped, 1 warning (Starlette TestClient/`httpx` deprecation).  
Includes new `test_mfa_route_gates.py` (10 passed). Later follow-on raised suite to 131 — see above.

### Reference foundation (separate discovery)

```text
PYTHONPATH=. python -m pytest -q tests/test_api.py tests/test_database.py tests/test_foundation.py
```

**Result:** 50 passed, 37 skipped, 13 subtests passed, 1 warning.  
Skips: native PostGIS/database cases without local DB — **not counted as pass**.

### OpenAPI + secret scan

```text
python scripts/export_active_openapi.py --check
→ Active OpenAPI contract matches

python scripts/secret_scan_light.py
→ SECRET_SCAN_HITS 0
```

### Active integration (not executed)

```text
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests tests/integration
```

**Blocker:** Docker unavailable; `TEST_DATABASE_URL` unset. IDOR suite file is present after merge but **not re-verified locally**.

### CI snapshot (PR #22 prior head `0c496a3`)

| Workflow | Conclusion |
| --- | --- |
| Active API smoke | SUCCESS |
| Active database security | SUCCESS |
| Reference foundation checks | SUCCESS |
| web workspace | SUCCESS |

Post-push CI for merge+new tests must be re-checked before merge.

### Historical CI cited (not re-run here)

- IDOR / DB acceptance: 223 passed @ `fc25eed` (SF-007 register).
- Earlier registers in `docs/implementation/VERIFICATION_REGISTER.md`.
