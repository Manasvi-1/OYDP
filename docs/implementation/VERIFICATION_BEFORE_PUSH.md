# Verification before push

Date: 2026-11-04. Branch: `feat/launch-1-drop-1`. HEAD: `95fce64798e7108cc4cf0b346f9f3e4a8df984ba`. Working tree already dirty before this run. No test file was edited. Nothing was committed.

Gate files read: `docs/implementation/IDENTITY_GATE.md`, `docs/implementation/SECURITY_REVIEW_GATE_0.md`, and `docs/implementation/SECURITY_GATES.md`.

## Decision

**Stop the release. Do not push this tree as verified.**

No executed web test, typecheck, production build, or API unit test failed. The required active API command also includes `tests/integration`. All 76 of those tests were skipped. Pytest exited 0 because the module skips itself when `TEST_DATABASE_URL` is unset. A skip is not a pass. Database acceptance is not inferred from this run.

## Environment

- Node `v20.18.0`, npm `10.8.2`.
- Python `3.11.9` at `C:\Users\WorkstationAdmin\AppData\Local\Programs\Python311\python.exe`.
- `python311._pth` contains `import site` and still ignores `PYTHONPATH`. A probe with `PYTHONPATH` set to `C:\Users\WorkstationAdmin\OYDP\apps\api` left `apps/api` off `sys.path` and did not import `pytest`.
- `pytest` is not installed in site-packages. The hash-locked tree at `C:\Users\WORKST~1\AppData\Local\Temp\oydp-api-deps` was already present. Compared with `apps/api/requirements.lock`: 28 packages, 0 missing, 0 version mismatches. This run did not reinstall it.
- `TEST_DATABASE_URL` was unset. `docker` is not on `PATH`. `psql` was not found under PostgreSQL 16 or 17. Docker Desktop’s `docker.exe` was not present.

## Web install

Working directory: `C:\Users\WorkstationAdmin\OYDP\apps\web`.

```text
npm ci
```

Exit code 0. `added 28 packages, and audited 29 packages in 58s`. The same install printed `2 vulnerabilities (1 moderate, 1 high)`. Detail is under the audit section below. `npm audit fix` was not run.

## Web contract tests

Working directory: `C:\Users\WorkstationAdmin\OYDP\apps\web`.

```text
npm test
```

That script is `node --test lib/contract.test.mjs lib/oidc.test.mjs`. Exit code 0. Node test report:

```text
# tests 8
# suites 0
# pass 8
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 169.5516
```

Counts: **8 passed, 0 failed, 0 skipped.**

The eight names split across the two files as written:

| File | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| `apps/web/lib/contract.test.mjs` | 5 | 0 | 0 |
| `apps/web/lib/oidc.test.mjs` | 3 | 0 | 0 |

Contract names that passed: local API base and tenant normalization; rejection of insecure remote bases, credentials, and malformed sessions; session round-trip and tampered-cookie rejection; API detail text with a fallback that does not echo unexpected bodies; bounded property and claim queries.

## Typecheck

Working directory: `C:\Users\WorkstationAdmin\OYDP\apps\web`.

```text
npm run typecheck
```

Script: `tsc --noEmit`. Exit code 0. No diagnostic output. This command does not emit pass, fail, or skip counts.

## Production web build

Working directory: `C:\Users\WorkstationAdmin\OYDP\apps\web`.

```text
$env:NEXT_TELEMETRY_DISABLED = '1'
npm run build
```

Script: `next build`. Exit code 0. Next.js `15.5.28` reported `Compiled successfully in 2.5s`, then generated 6 static pages. Routes reported: `/`, `/_not-found`, `/callback`, `/icon.svg`, `/login`, `/properties`, `/properties/[id]`, `/properties/new`. This command does not emit pass, fail, or skip counts.

## Active API tests

The Linux CI form `PYTHONPATH=apps/api:. python -m pytest apps/api/tests tests/integration` cannot start on this interpreter: `PYTHONPATH` is ignored and `python -m pytest` has no `pytest` module. The command that ran injects the repository, `apps/api`, and the locked target onto `sys.path`.

Working directory printed by the command: `C:\Users\WorkstationAdmin\OYDP`.

```text
python -c "import sys; sys.path[:0] = [r'C:\Users\WorkstationAdmin\OYDP\apps\api', r'C:\Users\WorkstationAdmin\OYDP', r'C:\Users\WORKST~1\AppData\Local\Temp\oydp-api-deps']; import pytest; raise SystemExit(pytest.main(['-q', 'apps/api/tests', 'tests/integration', '-ra', '--tb=line']))"
```

Exit code 0. Pytest summary:

```text
55 passed, 76 skipped, 1 warning in 3.16s
```

Counts: **55 passed, 0 failed, 76 skipped.** One warning, not a failure:

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

Source: `C:\Users\WORKST~1\AppData\Local\Temp\oydp-api-deps\fastapi\testclient.py:1`.

Every skip line names `tests\integration\test_database.py` and the reason `TEST_DATABASE_URL is required for real PostgreSQL tests`. The 55 passes are the tests collected from `apps/api/tests`. An earlier run of the same arguments, before this cwd was printed, reported the same counts in 4.86s. The PostgreSQL cases did not execute in either run.

## Dependency audit observed during install

Not one of the four named commands. Recorded because `npm ci` reported vulnerabilities. Working directory: `C:\Users\WorkstationAdmin\OYDP\apps\web`.

```text
npm audit
```

Exit code 1. npm metadata: **0 info, 0 low, 1 moderate, 1 high, 0 critical** (total 2). Installed `next` is `15.5.28`. Installed `postcss` is `8.4.31`, which is inside the vulnerable range `<=8.5.22`. `next` is the direct dependency; `postcss` is transitive.

| Package | npm severity | Advisories named in the report |
| --- | --- | --- |
| `postcss` | high | GHSA-qx2v-qp2m-jg93 (moderate, XSS in CSS stringify, `<8.5.10`); GHSA-6g55-p6wh-862q (high, `sourceMappingURL` file read, `<=8.5.11`); GHSA-fxqj-rqcc-2cmp (moderate, incomplete fix of that file read, `<=8.5.22`); GHSA-r28c-9q8g-f849 (high, source-map path traversal, `<=8.5.17`) |
| `next` | moderate | Via `postcss` only. Reported range `9.3.4-canary.0 - 16.3.0-preview.10` |

`npm audit` says a fix would install `next@16.4.5`, a semver-major change. That upgrade was not applied.

`pip-audit` was not run.

## Checks that could not run

- Real PostgreSQL execution of `tests/integration/test_database.py`. Blocker: `TEST_DATABASE_URL` unset, and no Docker or local `psql` on this machine. Pytest collected the module and skipped 76 tests.
- The workflow command `PYTHONPATH=apps/api:. python -m pytest -q apps/api/tests` from `API smoke`, for the reason in the API section.
- `python scripts/export_active_openapi.py --check` and `python -m compileall -q apps/api/app scripts`.
- `pip-audit -r apps/api/requirements.lock`.
- Reference-backend tests: `PYTHONPATH=. python -m pytest tests/test_api.py tests/test_database.py tests/test_foundation.py`.
- Keycloak start and browser enrollment. Docker is not installed. `IDENTITY_GATE.md` already records that limit.
- A browser walk of the workspace, login, logout, or the dev-server bind address.
- GitHub Actions for this HEAD. `API smoke` and `Database security` run on pull requests and on pushes to `main` and `feat/property-identity-foundation`. A local file does not create those runs. `web workspace` runs on every push and pull request; it was not invoked from here.

## Gate notes this run does not clear

`SECURITY_REVIEW_GATE_0.md` is a conditional pass with two blocking findings: the session cookie is an unsigned copy of the access token sent to a caller-chosen API base, and `npm run dev` is not bound to loopback. This run did not start the dev server and did not re-test those paths. Those findings stay as written in that file.

`SECURITY_GATES.md` still requires real PostgreSQL tenant-isolation tests, an audit outbox before real documents, and evidence upload to stay disabled. The skipped integration file is the local database evidence, and it did not run. `IDENTITY_GATE.md` remains a local verifier configuration plus unit tests, not an enrolled provider.

This file is a local command log. It is not production approval, an independent review, or a green database acceptance.
