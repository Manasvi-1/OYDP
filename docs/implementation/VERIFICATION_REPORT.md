# Verification report — live Keycloak + cross-tenant IDOR

Branch: `security/live-keycloak-and-tenant-idor` @ `fc25eed` (+ docs commit on this report)  
Base: PR #17 head `f5cf84e35a469ed918172fe55dbe3240bca69f8d` (OPEN; CI green)  
Prior increment (PR #17): MFA freshness via `auth_time` — kept separate; not merged by this work.  
PR: https://github.com/Manasvi-1/OYDP/pull/19

## CI acceptance (GitHub)

Failed run on `5bffd87` (`https://github.com/Manasvi-1/OYDP/actions/runs/42911387190`): **1 failed, 222 passed** — `test_role_privilege_escalation_and_pagination_cursor_isolation` expected property-scoped viewer claim denial as `403` but the API correctly returns non-disclosing `404`. Fixed in `fc25eed` (test expectation aligned; controls not weakened).

Green run on `fc25eed` Active database security (`https://github.com/Manasvi-1/OYDP/actions/runs/42919307872`): **223 passed**, 0 failed, 0 skipped (JUnit `database.xml`). Companion PR checks also green: Active API smoke, web workspace, Reference foundation checks.

## Commands and results (local Windows)

Worktree used so interview-demo uncommitted files stay on `feat/interview-demo-workspace`: `C:\Users\WorkstationAdmin\OYDP-security-wt`  
Interpreter: `C:\Users\WorkstationAdmin\OYDP\.venv\Scripts\python.exe` (3.11)  
`PYTHONPATH=apps/api;.` for active suites; `PYTHONPATH=.` for reference suites.

### Active API unit suite

```text
PYTHONPATH=apps/api;. python -m pytest -q apps/api/tests --tb=line -ra
```

Result: **116 passed**, 0 failed, 0 skipped. 1 Starlette TestClient deprecation warning.

### Reference suite (frozen `oydp/`)

```text
PYTHONPATH=. python -m pytest -q tests/test_api.py tests/test_foundation.py --tb=line -ra
```

Result: **50 passed**, 0 failed, 0 skipped, **13 subtests passed**. 1 Starlette deprecation warning.

### Integration / PostgreSQL / IDOR matrix (local)

```text
PYTHONPATH=apps/api;. python -m pytest -q tests/integration --tb=line -ra
```

Result: **107 skipped**, 0 passed, 0 failed. Reason: `TEST_DATABASE_URL is required for real PostgreSQL tests`.  
A local `postgres` process may listen on `5432`, but no untracked `.env` / disposable `TEST_DATABASE_URL` was configured for this run, so local native execution stayed skipped. Skipped ≠ passed. Native PostGIS CI (above) is the acceptance authority for the IDOR matrix (`tests/integration/test_z_cross_tenant_idor.py`, 8 cases; `test_z_` ordering after `test_database`).

### Web security unit tests

```text
node --test apps/web/lib/session-security.test.mjs apps/web/tests/proxy.test.mjs apps/web/lib/api-client.test.mjs
```

Result: **19 passed**, 0 failed, 0 skipped.

### Live Keycloak

```text
python scripts/verify_live_keycloak_mfa.py
```

Result: **BLOCKED** — exit 2; identity provider connection refused (`127.0.0.1:8080`). Docker Desktop client present; engine pipe unavailable (`npipe:////./pipe/docker_engine`); no WSL distro. Attempted Desktop launch did not bring the daemon up in-session. No synthetic JWT substituted as live proof.

### Secret scan (lightweight)

```text
python scripts/secret_scan_light.py
```

Result: **SECRET_SCAN_HITS 0**, exit 0.

## Maturity

Executable MFA production-config guard and expanded IDOR regression matrix. Native PG IDOR matrix **VERIFIED in CI** (223/0). Live IdP MFA claim emission **BLOCKED** locally. Not production-hardened. Not independently reviewed.
