# OYDP private property workspace

Draft Next.js frontend for the active API 0.4.0. Requires Node 22+ and the active FastAPI service plus migrated PostgreSQL runtime role. No browser sign-in provider is bundled.

```sh
cd apps/web
npm ci
OYDP_API_ORIGIN=http://127.0.0.1:8000 npm run dev
```

Open http://127.0.0.1:3000. Use an operator-issued API access token and an existing tenant UUID. The backend requires configured HTTPS JWKS/issuer/audience, RS256 `at+jwt` access tokens, current membership, and signed `amr: ["mfa"]` for writes. Never use production records/tokens in test fixtures. No API URL or service secret is exposed through NEXT_PUBLIC variables.

```sh
npm test
npm run build
npm start
```

The proxy accepts only a fixed HTTPS upstream or local loopback HTTP. Credentials remain in React memory, cleared on disconnect/reload/401. Run privately over HTTPS outside loopback. There is no tenant/user provisioning bypass. API responses and pages carry no-store headers. HTML responses use a fresh 256-bit nonce CSP with dynamic rendering; production scripts/styles require a matching nonce, and inline/eval bypasses are disabled. The development server permits eval for framework debugging. Caller-provided nonce/CSP headers are replaced. Browser provider login remains pending. No analytics or external fonts are loaded.

See `docs/implementation/POST_PR4_AUDIT.md` for verified baseline and outstanding acceptance gates. The absence of live identity/provider browser tests prevents a production-ready claim.

Browser acceptance: `npm run test:e2e` requires an explicitly disposable native PostgreSQL database named `oydp_web_e2e`, TEST_DATABASE_URL and OYDP_BROWSER_DISPOSABLE=yes. It generates ephemeral credentials under ignored `.e2e/`, starts the actual API and production Next server, and substitutes only test JWKS transport. Never run the harness against a shared database. CI provisions the disposable service.
