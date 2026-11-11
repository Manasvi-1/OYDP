# Start the interview demo locally

Use disposable databases only. Never point these commands at shared or production data.

## Prerequisites

- Python 3.11+, Node 20+, PostgreSQL/PostGIS
- Disposable database name containing `demo`, `e2e`, or `test`

## One-time setup

```bash
cp .env.example .env
# Fill POSTGRES_PASSWORD, RUNTIME_DATABASE_PASSWORD, DOCUMENT_STORAGE_KEY,
# and generate SESSION_KEY:
# node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"

export MIGRATION_DATABASE_URL='postgresql://postgres:PASSWORD@127.0.0.1:5432/oydp_demo'
export RUNTIME_DATABASE_PASSWORD='at-least-24-random-characters'
python scripts/migrate.py --provision-runtime

export OYDP_DEMO_SEED_ALLOW=yes
export DEMO_DATABASE_URL="$MIGRATION_DATABASE_URL"
export RUNTIME_DATABASE_PASSWORD  # optional reprovision during seed
python scripts/seed_demo.py
```

Seed prints the synthetic tenant UUID for subject `alice`.

## Reset synthetic data

```bash
export OYDP_DEMO_SEED_ALLOW=yes
export DEMO_DATABASE_URL='postgresql://postgres:PASSWORD@127.0.0.1:5432/oydp_demo'
python scripts/seed_demo.py
```

## Run API + optional loopback OIDC + web

```bash
export OYDP_DEV_OIDC=1
export OYDP_DEV_OIDC_ISSUER=http://127.0.0.1:9000
export OYDP_DEV_OIDC_AUDIENCE=oydp-api
export OYDP_DEV_OIDC_CLIENT_ID=oydp-web
export OYDP_DEV_OIDC_REDIRECTS=http://127.0.0.1:3000/callback
python tools/dev_oidc.py

export OYDP_OIDC_DEV_HTTP=1
export OIDC_ISSUER=http://127.0.0.1:9000
export OIDC_AUDIENCE=oydp-api
export OIDC_JWKS_URL=http://127.0.0.1:9000/.well-known/jwks.json
export DATABASE_URL='postgresql://oydp_app:RUNTIME_PASSWORD@127.0.0.1:5432/oydp_demo'
export DOCUMENT_STORAGE_KEY='...' # 32-byte urlsafe base64
cd apps/api
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000

cd apps/web
npm ci
export SESSION_KEY='...' # 32-byte base64url
export OIDC_CLIENT_ID=oydp-web
export OIDC_REDIRECT_URI=http://127.0.0.1:3000/callback
export OIDC_AUDIENCE=oydp-api
export OIDC_ISSUER=http://127.0.0.1:9000
export OIDC_JWKS_URL=http://127.0.0.1:9000/.well-known/jwks.json
export PROPERTY_API_BASE=http://127.0.0.1:8000
# Required for http://127.0.0.1 when using `npm run start` (NODE_ENV=production).
# Leave unset for real HTTPS deployments.
export OYDP_COOKIE_SECURE=0
npm run dev
```

Open `http://127.0.0.1:3000`.

Sign-in path:

1. Click **Sign in**, subject `alice`, optionally set MFA checkbox for writes.
2. Enter the seeded tenant UUID on `/connect`.
3. Or paste a separately minted access token on `/` with the tenant UUID.

## Checks

```bash
cd apps/web && npm test && npm run typecheck && npm run build
PYTHONPATH=apps/api:. python -m pytest -q apps/api/tests
```

Browser journey (disposable DB only):

```bash
export TEST_DATABASE_URL='postgresql://postgres:PASSWORD@127.0.0.1:5432/oydp_web_e2e'
export OYDP_WEB_E2E_ALLOW=yes
cd apps/web && npx playwright install chromium
cd ../.. && python scripts/run_web_e2e.py
```
