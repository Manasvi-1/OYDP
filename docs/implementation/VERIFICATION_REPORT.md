# Verification report — MFA freshness hardening

Branch: `feat/mfa-freshness-hardening`  
Base: `887cc871a2a8bf03515a7f7c14218bf0a6f27dcb` (origin/main, PR #16)

## Commands and results (local Windows)

Working directory: `C:\Users\WorkstationAdmin\OYDP`  
Interpreter: `.venv\Scripts\python.exe` (3.11.9)  
`PYTHONPATH=apps/api;.` for active suites; `PYTHONPATH=.` for reference suites.

### Baseline before edits (auth/documents/canonical/dev-oidc)

```text
python -m pytest -q apps/api/tests/test_auth.py apps/api/tests/test_canonical_authority.py apps/api/tests/test_dev_oidc.py apps/api/tests/test_documents.py --tb=no -ra
```

Result: **82 passed**, 0 failed, 0 skipped. 1 Starlette TestClient deprecation warning.

### After implementation — full active API unit suite

```text
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests --tb=line -ra
```

Result: **115 passed**, 0 failed, 0 skipped. 1 Starlette TestClient deprecation warning. Elapsed ~7.2s.

### Reference suite (frozen `oydp/`)

```text
PYTHONPATH=. python -m pytest -q tests/test_api.py tests/test_foundation.py --tb=line -ra
```

Result: **50 passed**, 0 failed, 0 skipped, **13 subtests passed**. 1 Starlette deprecation warning. Elapsed ~1.1s.

Separate discovery; not interchangeable with the active API.

### Integration / PostgreSQL

```text
PYTHONPATH=apps/api;. python -m pytest -q tests/integration --tb=line -ra
```

Result: **99 skipped**, 0 passed, 0 failed. Reason: `TEST_DATABASE_URL is required for real PostgreSQL tests`. Native PostGIS CI remains the authority for DB/RLS acceptance; skipped local cases are not counted as passed.

## Maturity

Executable MFA freshness controls with unit/dev-issuer coverage. Not production-hardened. Not independently reviewed. Live IdP enrollment NOT VERIFIED.
