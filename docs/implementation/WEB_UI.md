# Authenticated web workspace

Pre-alpha Next.js workspace for the active property API. It signs in with the access-token profile the API already verifies, lists private properties, opens one record, and records unverified claims. It does not certify title, select a production identity provider, or complete the later evidence, document, audit, or collaboration journeys.

Open pull requests #5 and #6 also contain workspace attempts. Both ask an operator to paste a bearer token. This workspace uses authorization code and PKCE instead, and it does not merge those branches.

## Trust boundaries

- The browser never receives the API base from a form, and it never stores the access token in JavaScript. The token is sealed with AES-GCM in an httpOnly cookie. `SESSION_SECRET` is an environment variable of at least 32 characters.
- Sign-in redirects to the configured issuer, checks `state`, exchanges the code with PKCE, and verifies the access token against the issuer JWKS before saving it. Accepted tokens are RS256 `typ=at+jwt` for the configured audience. An ID token is not sent to the API. If a provider also returns an ID token, its nonce must match the sign-in transaction.
- Discovery and token URLs must stay on the issuer origin. The property API base must be https, or loopback http, with no credentials and no path prefix.
- Tenant membership stays in the database. After sign-in the person enters the provisioned tenant UUID. The server confirms it with `GET /v1/properties?limit=1`. A wrong tenant is rejected. The workspace cannot create memberships.
- Property and claim text is rendered as text. Pagination cursors are allowlisted before they are sent. API failures become a fixed set of messages; response bodies are not copied into the page.
- Creating a property or recording a claim still depends on the API's MFA claim. The development issuer can set `amr` from a checkbox. That checkbox is not an authenticator. A production provider has to assert MFA itself.
- `OYDP_OIDC_DEV_HTTP=1` lets the API accept `http://127.0.0.1` or `http://localhost` issuer and JWKS URLs. Any other host, userinfo, query, or fragment stays invalid. Unset the flag for a real https issuer.

## Local run

Use a disposable database and synthetic labels. Memberships are inserted by an administrator, not by the UI.

```bash
cp .env.example .env
# Fill POSTGRES_PASSWORD, RUNTIME_DATABASE_PASSWORD, SESSION_SECRET, and the OIDC values below.
docker compose up -d db
export MIGRATION_DATABASE_URL='postgresql://postgres:PASSWORD@127.0.0.1:5432/oydp'
export RUNTIME_DATABASE_PASSWORD='at-least-24-random-characters'
python scripts/migrate.py --provision-runtime
# Insert a synthetic membership with the migration role, for example subject "alice", role owner.

export OYDP_DEV_OIDC=1
export OYDP_DEV_OIDC_ISSUER=http://127.0.0.1:9000
export OYDP_DEV_OIDC_AUDIENCE=oydp-api
export OYDP_DEV_OIDC_CLIENT_ID=oydp-web
export OYDP_DEV_OIDC_REDIRECTS=http://127.0.0.1:3000/auth/callback
python tools/dev_oidc.py

export OYDP_OIDC_DEV_HTTP=1
export OIDC_ISSUER=http://127.0.0.1:9000
export OIDC_AUDIENCE=oydp-api
export OIDC_JWKS_URL=http://127.0.0.1:9000/.well-known/jwks.json
export DATABASE_URL='postgresql://oydp_app:RUNTIME_PASSWORD@127.0.0.1:5432/oydp'
PYTHONPATH=apps/api uvicorn app.main:app --host 127.0.0.1 --port 8000

cd apps/web
npm ci
export SESSION_SECRET='at-least-32-random-characters-here'
export OIDC_CLIENT_ID=oydp-web
export OIDC_REDIRECT_URI=http://127.0.0.1:3000/auth/callback
export PROPERTY_API_BASE=http://127.0.0.1:8000
npm run dev
```

Open `http://127.0.0.1:3000`. Sign in with a development subject that matches the membership. The development page can set the MFA claim for local write tests. Then enter the tenant UUID.

To point the same UI at another issuer, use https URLs, leave `OYDP_OIDC_DEV_HTTP` unset, and configure that issuer to issue this API's access-token profile. Choosing that provider is an owner decision. No vendor is configured in this repository.

## Tests

```bash
PYTHONPATH=apps/api:. python -m pytest -q apps/api/tests
cd apps/web && npm test && npm run typecheck && npm run build
```

The browser journey needs a disposable Postgres database whose name contains `e2e` or `test`:

```bash
export TEST_DATABASE_URL='postgresql://postgres:PASSWORD@127.0.0.1:5432/oydp_web_e2e'
export OYDP_WEB_E2E_ALLOW=yes
python -m pip install --require-hashes -r apps/api/requirements.lock
cd apps/web && npm ci && npx playwright install chromium
cd ../.. && python scripts/run_web_e2e.py
```

The script migrates that database, clears synthetic tenant rows, provisions `oydp_app`, inserts synthetic `alice` and `mallory` memberships, starts the development issuer, API, and production Next server, then runs the Playwright journey. It refuses to start without `OYDP_WEB_E2E_ALLOW=yes`.

## Rollback

The workspace adds no migration. Remove `apps/web`, `tools/dev_oidc.py`, `scripts/run_web_e2e.py`, and `.github/workflows/web.yml`, and restore `apps/api/app/auth.py` if the loopback flag should disappear with the UI. Existing property data and API 0.4.0 behavior for https issuers stay in place. Unset `OYDP_OIDC_DEV_HTTP` before any shared deployment.

## Still open

Production provider selection, authenticator enrollment, MFA freshness, logout at the provider, token revocation, tenant directory, write delegation, evidence lineage, private documents, audit delivery, and the rest of the 13 engines. Passing these tests is not production approval.
