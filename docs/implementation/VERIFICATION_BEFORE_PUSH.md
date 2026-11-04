# Verification before push

Date: 2026-11-04. Branch: `feat/launch-1-drop-1`. HEAD at the start of this run: `95fce64798e7108cc4cf0b346f9f3e4a8df984ba`. Nothing was committed.

Gate files read: `docs/implementation/IDENTITY_GATE.md`, `docs/implementation/SECURITY_REVIEW_GATE_0.md`, and `docs/implementation/SECURITY_GATES.md`.

## Decision

The checks that stopped the earlier pass have now executed.

Active API tests: **171 passed, 0 failed, 0 skipped**. Reference backend tests: **87 passed, 0 failed, 0 skipped**, plus **13 subtests passed**. The clean web install, contract tests, typecheck, and production build succeeded. `npm audit` reported **0 vulnerabilities**.

This is still not production approval, an independent review, or an enrolled identity provider. Keycloak was not started. The session cookie remains an unsigned copy of the access token, which `SECURITY_REVIEW_GATE_0.md` treats as blocking once the web process is reachable beyond this computer. `dev` and `start` are now bound to `127.0.0.1`.

## What changed so the database suite could pass

`infra/db/011_write_grant_pages.sql` now also defines `actor_has_live_write_grant`. The property read policy allows the creator, a live read grant, or that live write grant. Direct `UPDATE` stays creator-only. The function reads grant rows as its owner so the policies do not recurse, and `INSERT ... RETURNING` can still see the new row. `scripts/migrate.py` grants `oydp_app` execute on that function, and grants the document quarantine functions that the runtime role calls.

`apps/web/package.json` pins `dev` and `start` to `--hostname 127.0.0.1` and overrides `postcss` to `8.5.32`. The lockfile resolves `postcss` `8.5.32`. Next.js stays `15.5.28`.

## Environment

- Node `v20.18.0`, npm `10.8.2`.
- Python `3.11.9`. `python311._pth` ignores `PYTHONPATH`, and `pytest` is not installed in site-packages. Commands inject `apps/api` or the repository root plus `C:\Users\WORKST~1\AppData\Local\Temp\oydp-api-deps`. That directory matches all 28 packages in `apps/api/requirements.lock`.
- PostgreSQL `16.15` portable binaries, loopback only, trust authentication for `127.0.0.1/32`. Cluster data was `C:\Users\WORKST~1\AppData\Local\Temp\oydp-pg\data`. The server was stopped after the tests.
- The Microsoft Visual C++ 2015–2022 x64 redistributable was installed so `initdb.exe` could start. Installer exit code 0.
- PostGIS is not in those binaries. The reference SQL does not use it. Those tests passed without `CREATE EXTENSION postgis`.
- Docker is not installed. Keycloak was not started.

## Web clean build

Working directory: `C:\Users\WorkstationAdmin\OYDP\apps\web`. `.next` was removed. `npm ci` replaced `node_modules`.

```text
npm ci
npm test
npm run typecheck
$env:NEXT_TELEMETRY_DISABLED = '1'
npm run build
npm audit
```

`npm ci` exit code 0: `added 28 packages, and audited 29 packages in 46s`, then `found 0 vulnerabilities`.

`npm test` exit code 0. Node report:

```text
# tests 8
# pass 8
# fail 0
# skipped 0
# todo 0
```

Counts: **8 passed, 0 failed, 0 skipped** (5 in `lib/contract.test.mjs`, 3 in `lib/oidc.test.mjs`).

`npm run typecheck` (`tsc --noEmit`) exit code 0. No diagnostics.

`npm run build` exit code 0. Next.js `15.5.28` compiled successfully in 11.7s and generated 6 pages. It warned that the lockfile was missing SWC optional dependencies and patched the lockfile during the build. The build still completed. Routes: `/`, `/_not-found`, `/callback`, `/icon.svg`, `/login`, `/properties`, `/properties/[id]`, `/properties/new`.

`npm audit` exit code 0: `found 0 vulnerabilities`.

## Active API tests

Disposable database `oydp_security_test` on `127.0.0.1:5432`. The database was dropped and recreated before the recorded run.

```text
$env:TEST_DATABASE_URL = 'postgresql://postgres@127.0.0.1:5432/oydp_security_test'
python -c "import sys; sys.path[:0] = [r'C:\Users\WorkstationAdmin\OYDP\apps\api', r'C:\Users\WorkstationAdmin\OYDP', r'C:\Users\WORKST~1\AppData\Local\Temp\oydp-api-deps']; import pytest; raise SystemExit(pytest.main(['-q', 'apps/api/tests', 'tests/integration', '-ra', '--tb=line']))"
```

Exit code 0.

```text
171 passed, 1 warning in 27.56s
```

Counts: **171 passed, 0 failed, 0 skipped**. The warning is `StarletteDeprecationWarning` from `fastapi/testclient.py` about `httpx` and `starlette.testclient`. It is not a failure.

An earlier run on the same server, before the write-grant read policy was in place, was **1 failed, 169 passed**. The failure was `test_delegated_editor_can_correct_and_append_only_while_granted`: the writers response had no `items` because a write grant alone could not read the property. The recorded run above is after that policy change.

## Reference backend tests

Empty database `oydp_ref_test`. Role `oydp_runtime` was created as a non-superuser without `BYPASSRLS`. Password used only in this process: `isolated-local-runtime-only`.

```text
$env:OYDP_TEST_ADMIN_DSN = 'postgresql://postgres@127.0.0.1:5432/oydp_ref_test'
$env:OYDP_TEST_RUNTIME_DSN = 'postgresql://oydp_runtime:isolated-local-runtime-only@127.0.0.1:5432/oydp_ref_test'
$env:OYDP_TEST_ALLOW_RESET = 'yes'
python -c "import sys; sys.path[:0] = [r'C:\Users\WorkstationAdmin\OYDP', r'C:\Users\WORKST~1\AppData\Local\Temp\oydp-api-deps']; import pytest; raise SystemExit(pytest.main(['-q','tests/test_foundation.py','tests/test_api.py','tests/test_database.py','-ra','--tb=line']))"
```

Exit code 0.

```text
87 passed, 1 warning, 13 subtests passed in 9.61s
```

Counts: **87 passed, 0 failed, 0 skipped**, **13 subtests passed**. Same Starlette deprecation warning.

## Other commands that ran

OpenAPI check, with the active API path injected:

```text
Active OpenAPI contract matches
```

Exit code 0.

`compileall` on `oydp`, `tests`, `apps/api/app`, and `scripts`: exit code 0.

OSV batch query of the 28 pinned distributions in `apps/api/requirements.lock`: **0 vulnerable packages**. `pip-audit==2.10.1` was installed under `C:\Users\WORKST~1\AppData\Local\Temp\oydp-pip-audit` but could not start: this Python install has no `venv` standard library (`Lib\venv` is absent), and `pip-audit` imports `venv` before it reads a requirements file.

## Not run

- Keycloak, browser enrollment, login, and logout. Docker is not installed.
- A browser walk of the workspace.
- `CREATE EXTENSION postgis`. The reference tests passed without it.
- GitHub Actions for this working tree.
- The JUnit acceptance guard `scripts/check_test_report.py`. Pytest itself reported zero skips and zero failures for both suites. A separate XML file was not verified.

## Still open

`SECURITY_REVIEW_GATE_0.md` finding 1 is unchanged: the session cookie is an unsigned copy of the access token, and a caller-chosen `https` API base is still accepted. Finding 2 is addressed in the npm scripts: `next dev` and `next start` listen on `127.0.0.1` only. Evidence upload, an audit outbox outside this database, and an enrolled identity provider are still absent. Do not treat this log as release approval.

## Session seal re-run — 2026-11-04

HEAD remains `95465978ca13877ec166a53c73bf8030b4a3642b`. The session changes are uncommitted. The paragraphs above are the earlier log and are left as written. This section records the commands after the session cookie was sealed and the API origin was taken only from `PROPERTY_API_BASE`.

The same PostgreSQL 16.15 cluster was started again for this run and stopped afterward. Databases `oydp_security_test` and `oydp_ref_test` were dropped and recreated first. `npm ci` was not repeated; `node_modules` was already present. Keycloak was not started, and the browser was not used.

From `apps/web`:

```text
npm test
npm run typecheck
$env:NEXT_TELEMETRY_DISABLED = '1'
npm run build
npm audit
```

`npm test` exit code 0: **13 passed, 0 failed, 0 skipped**. `npm run typecheck` exit code 0. `npm run build` exit code 0 (Next.js 15.5.28, compiled in 3.0s, same 6 pages). `npm audit` exit code 0: `found 0 vulnerabilities`.

Active API command, exit code 0: **171 passed, 0 failed, 0 skipped**, 1 Starlette warning, 25.92s. Reference command, exit code 0: **87 passed, 0 failed, 0 skipped**, **13 subtests passed**, 1 Starlette warning, 8.92s. OpenAPI `--check` exit code 0: `Active OpenAPI contract matches`.

A copy of `contract.mjs` from HEAD accepts an unsigned cookie whose payload sets `apiBase` to `https://evil.example`, and it accepts that origin in `parseSessionInput`. The current tests reject both. That probe is the evidence that the new assertions fail on the previous codec. It is not a browser or Keycloak login.
