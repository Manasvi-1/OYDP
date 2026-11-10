# Verification report — live Keycloak + cross-tenant IDOR

Branch: `security/live-keycloak-and-tenant-idor`  
Base: PR #17 head `f5cf84e35a469ed918172fe55dbe3240bca69f8d` (OPEN; CI green at verification time)  
Prior increment (PR #17): MFA freshness via `auth_time` — kept separate; not merged by this work.

## Commands and results (local Windows)

Working directory: `C:\Users\WorkstationAdmin\OYDP`  
Interpreter: `.venv\Scripts\python.exe` (3.11)  
`PYTHONPATH=apps/api;.` for active suites; `PYTHONPATH=.` for reference suites.

### Active API unit suite

```text
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests --tb=line -ra
```

Result: **116 passed**, 0 failed, 0 skipped. 1 Starlette TestClient deprecation warning.

Focused auth subset earlier in the same session: **61 passed** (`test_auth` + canonical + DevOidc).

### Reference suite (frozen `oydp/`)

```text
PYTHONPATH=. python -m pytest -q tests/test_api.py tests/test_foundation.py --tb=line -ra
```

Result: **50 passed**, 0 failed, 0 skipped, **13 subtests passed**. 1 Starlette deprecation warning.

### Integration / PostgreSQL / IDOR matrix

```text
PYTHONPATH=apps/api;. python -m pytest -q tests/integration --tb=line -ra
```

Result: **107 skipped**, 0 passed, 0 failed. Reason: `TEST_DATABASE_URL is required for real PostgreSQL tests`.  
Includes new file `tests/integration/test_cross_tenant_idor.py` (8 cases). Skipped ≠ passed. Native PostGIS CI remains the acceptance authority.

### Web security unit tests

```text
node --test apps/web/lib/session-security.test.mjs apps/web/tests/proxy.test.mjs apps/web/lib/api-client.test.mjs
```

Result: **19 passed**, 0 failed, 0 skipped.

### Live Keycloak

```text
python scripts/verify_live_keycloak_mfa.py
```

Result: **BLOCKED** — identity provider connection refused (`127.0.0.1:8080`). Docker Desktop client present; engine pipe unavailable; no WSL distro; ports 5432/8080 closed. No synthetic JWT substituted as live proof.

### Secret scan (lightweight)

```text
python scripts/secret_scan_light.py
```

Result recorded at push time in the PR body / final delivery.

## Maturity

Executable MFA production-config guard and expanded IDOR regression matrix. Live IdP MFA claim emission **BLOCKED** locally. Native PG IDOR execution **NOT VERIFIED** locally (deferred to CI). Not production-hardened. Not independently reviewed.
