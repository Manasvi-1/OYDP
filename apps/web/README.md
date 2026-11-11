# OYDP private property workspace

Authenticated Next.js workspace for the active Property Identity API (**0.17.0**). Requires Node 20+, the FastAPI service in `apps/api`, and a migrated PostgreSQL database with role `oydp_app`.

## Local run

```sh
cd apps/web
npm ci
# Configure PROPERTY_API_BASE, SESSION_KEY, and OIDC settings in the repo-root .env (see .env.example).
npm run dev
```

Open http://127.0.0.1:3000. Local demos may paste an operator-issued access token and tenant UUID, or use loopback OIDC when configured. The API still requires RS256 `at+jwt` tokens, membership, and MFA freshness for high-risk writes. Never use production records or tokens in fixtures. No API origin or secret is exposed through `NEXT_PUBLIC_*` variables.

```sh
npm test
npm run typecheck
npm run build
npm start
```

## Security notes

- Sessions are AES-GCM sealed httpOnly cookies (`SESSION_KEY`). Tokens are not kept in React memory or `localStorage`.
- `PROPERTY_API_BASE` is server configuration only; the browser cannot choose another origin.
- `middleware.js` issues a fresh CSP nonce per HTML request and replaces forged caller CSP headers. Production scripts disallow `unsafe-inline` / `unsafe-eval`.
- Documented CSP details: `docs/implementation/WEB_CSP.md`.

## Browser e2e

Playwright harnesses under `e2e/` require an explicitly disposable database and local API/web processes. Prefer the commands documented in `docs/interview/START_LOCAL.md`. Do not point the harness at a shared database.

This workspace is pre-alpha. CSP and session controls are defense in depth, not production certification.
