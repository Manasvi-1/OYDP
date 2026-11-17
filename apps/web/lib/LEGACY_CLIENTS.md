# Legacy client modules (test-only)

These modules are **not** used by the App Router workspace path (`lib/api.ts`, `lib/contract.mjs`, `lib/session.ts`).

They remain for focused unit tests of older client helpers:

- `api-client.mjs` + `api-client.test.mjs`
- `fields.mjs` + `fields.test.mjs`
- `records.mjs` + `records.test.mjs`
- `session-cookie.mjs` + `session-cookie.test.mjs`
- `proxy.mjs` (API path proxy helper) + `tests/proxy.test.mjs`

Do not wire them into `app/` routes without reconciling schemes, env names (`SESSION_KEY` vs `SESSION_SECRET`), and path allowlists with the live stack. Removing them would drop coverage from `npm test` without improving the production path.
