# Test evidence

Only executed results are recorded. Skipped suites are named. Passing tests are not production approval.

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
