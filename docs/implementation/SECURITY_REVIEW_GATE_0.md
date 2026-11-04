# Security review gate 0 — current branch

Date: 2026-11-04. Branch: `feat/launch-1-drop-1`. HEAD: `95fce64798e7108cc4cf0b346f9f3e4a8df984ba`. Merge-base with `main`: `542cc8973e2d8e9650eb90ffde141940c133e2ce`. The review includes that committed diff and the uncommitted working tree (OIDC callback, correction and write-grant migration, Keycloak realm, workspace actions).

This is a static engineering review of the tree against `docs/THREAT_MODEL.md`, `docs/implementation/SECURITY_GATES.md`, the active API in `apps/api`, and the web session path in `apps/web`. It is not an independent audit, a penetration test, or a production approval. No tests were weakened or deleted. Nothing was committed.

Fundraising “gate 0” in `docs/fundraising/FUNDER_PROPOSAL.md` is a rights opinion. This file does not supply that opinion.

## Decision

**Conditional pass** for further local work on this branch by the operator of this machine.

The condition is narrow. The property API still resolves the caller from a verified access token and a database membership row, and the new write-grant and correction functions fail closed for the cases read below. The web process does not. It will attach the bearer token to a caller-chosen origin, and `npm run dev` does not bind that process to loopback.

**Stop** if either blocking finding below is still true when any other person or any other machine can open the web process. That includes a LAN address, a reverse proxy, a pilot, or a shared login on this workstation.

### Blocking findings

1. **The session cookie is an unsigned copy of the access token, and the server will send that token to an origin the caller picks.** `parseSessionInput` accepts any `https` origin, plus `http` on `localhost` or `127.0.0.1`. `encodeSession` stores `{apiBase, tenantId, accessToken}` as base64url JSON. `callPropertyApi` fetches `session.apiBase` with `Authorization: Bearer` and `X-Tenant-ID`. The connect form on `/` always posts those three fields, including when OIDC is configured. After the cookie is written, changing `apiBase` to another accepted origin is still a valid cookie. The unit test named as a tamper check only rejects cookies that fail to parse.
   - `apps/web/lib/contract.mjs`
   - `apps/web/lib/session.ts`
   - `apps/web/lib/api.ts`
   - `apps/web/app/actions.ts` (`connectSession`)
   - `apps/web/app/page.tsx`
   - `apps/web/lib/contract.test.mjs`
2. **The workspace dev server is not pinned to loopback.** Postgres and Keycloak publish `127.0.0.1` only (`compose.yaml`). `apps/web/package.json` runs `next dev --port 3000` with no hostname. Next.js 15.5.4 passes that unset hostname to `server.listen`. Node then listens on the unspecified address. Together with finding 1, another host that can reach the dev port can ask this machine to request `http://127.0.0.1:<port>/v1/...` and can submit an access token to an origin it chooses. This review did not start the dev server.

## What was reviewed

Threat model, security gates, `apps/api/app/auth.py`, `apps/api/app/main.py`, `apps/api/tests/test_auth.py`, `infra/db/006_private_property_access.sql`, `infra/db/008_property_corrections.sql`, `scripts/migrate.py`, `tests/integration/test_database.py` (the new correction and writer cases, read only), `apps/web` session, OIDC, server actions, and response headers, `infra/keycloak/oydp-realm.json`, `compose.yaml`, `.env.example`, and the GitHub workflows under `.github/workflows`. A search of the branch diff and realm file found no private keys, cloud access keys, or live passwords. `.env.example` and the Keycloak admin variable are placeholders. `.env` is gitignored.

Checks not done: pytest, `npm test`, a browser login or logout, a running Keycloak, a secret-scanner binary, dependency audit execution, and any attempt to exploit the running stack.

## Implemented controls

These are present in the code that was read. Presence is not evidence that the surrounding CI job has been run on this branch.

**API identity.** `verified_claims` requires configured issuer, audience, and JWKS. Remote issuer and JWKS URLs must be `https`. `http` is accepted only for host `localhost` or `127.0.0.1`, with no userinfo and no fragment. Tokens must be `Bearer`, RS256, `typ=at+jwt`, with `kid`, and without `crit`. `jku` and `x5u` are not used. `iss`, `aud`, `sub`, `exp`, and `iat` are required. `amr` must be a list of strings. Unit tests cover expiry, audience, issuer, subject length, forged signatures, ID-token `typ`, `crit`, JWKS failure, and the localhost HTTP exception. Mutating routes call `require_mfa` and accept `mfa` or `otp` in `amr`. Reads do not.

**Tenant and object authorization.** `authorized_db` takes `X-Tenant-ID` and the verified `sub`, sets both as transaction-local settings, and selects `tenant_memberships` for that pair. Missing membership is 403. The connection is refused unless `current_user` is `oydp_app` and that role is not superuser and not `BYPASSRLS`. Property reads use the creator or an unexpired, unrevoked read grant, under `FORCE ROW LEVEL SECURITY`. Read and write changes go through `SECURITY DEFINER` functions with `search_path` fixed to `pg_catalog, pg_temp`. Both functions require the tenant argument to match `app.tenant_id`, an owner or editor membership, and `created_by` equal to the actor. They reject a self-grant, a blank recipient, and an expiry outside the next 30 days. Write delegation also requires the recipient to be an owner or editor in the same tenant. `REVOKE ALL ... FROM PUBLIC` is in the migration. `scripts/migrate.py` grants execute, and select plus a lock-only column update, to `oydp_app` only. Direct inserts into write grants and corrections are not granted. Update policies on grants and memberships use `WITH CHECK(false)`. Request bodies use `extra='forbid'`. Queries that take ids use parameters.

**Web boundaries that do exist.** The session cookie is `httpOnly`, `SameSite=lax`, `Path=/`, eight hours, and `Secure` when `NODE_ENV` is `production`. Browser JavaScript in this app does not read the token. Property and token-endpoint fetches use `redirect: 'manual'` and an eight-second timeout. Paths passed to the property fetch must start with `/v1/`. OIDC login stores `state`, `nonce`, and the PKCE verifier in a separate `httpOnly` cookie scoped to `Path=/callback` for ten minutes. The authorize request uses S256. The callback checks `state` before exchanging the code. The realm client `oydp-web` is public, has no client secret in the import, disables implicit flow and direct access grants, and limits redirect URIs to the local callback. Keycloak and Postgres ports in Compose are `127.0.0.1`. Response headers on the web app set `nosniff`, `no-referrer`, `X-Frame-Options: DENY`, and a locked permissions policy. The API sets `Cache-Control: no-store` and `nosniff`. Property pages render claim text as React text. The notice banner is an allowlist. Property ids in server actions are checked as UUIDs.

**Product claims.** Screens and `docs/implementation/LAUNCH_1_DROP_1.md` say the workspace does not verify title and does not speak for a government office. Evidence upload is still absent.

## Automated checks

| Check | Where it lives | What this review can say |
| --- | --- | --- |
| Access-token unit tests | `apps/api/tests/test_auth.py`, workflow `API smoke` | The tests are in the tree. They were not executed here. `API smoke` runs on pull requests and on pushes to `main` and `feat/property-identity-foundation`. A push to `feat/launch-1-drop-1` does not match that branch filter. |
| RLS, grants, MFA, revocation, corrections, writers | `tests/integration/test_database.py`, workflow `Database security` | Same trigger gap. The new writer test expects a delegated editor, with no read grant, to list writers and `PATCH` the property. The property `SELECT` policy still allows only the creator or a live read grant (`infra/db/006_private_property_access.sql`). On a static reading the API returns 404 before the write-grant check. That is fail-closed. It also means the new test, if run, is the evidence of whether delegation works. This review did not run it. |
| Session and OIDC URL tests | `apps/web/lib/contract.test.mjs`, `apps/web/lib/oidc.test.mjs`, workflow `web workspace` | `web workspace` runs on every push and pull request. It was not executed here. `contract.test.mjs` accepts a normal `https` API base and rejects remote `http`, credentials, query strings, and a non-UUID tenant. A rewritten cookie with a different valid `https` origin still decodes. |
| Reference-backend job | workflow `foundation checks` | Runs on every push. It targets the root `oydp/` tests and role `oydp_runtime`, which is not the active `apps/api` role `oydp_app`. A green run there does not exercise this diff. |
| Dependency audit | `pip-audit` in `API smoke` | Not executed here. |
| Secret scan | — | No secret-scanning job is in the workflows that were read. The manual search above is not a scanner result. |

`docs/implementation/PROPERTY_API.md` records an older local pytest count. This review does not reuse that count.

## Open risks

These are not the blocking findings above. They are unresolved, and several of them become blocking the moment the process leaves the operator’s loopback.

**OIDC response binding is incomplete.** `readUnverifiedStringClaim` base64-decodes a JWT payload and does not check the signature, issuer, audience, or expiry. The callback uses it for the `id_token` nonce and for `tenant_id` on the access token. The property API does verify the access token on the probe call before `writeSession`. A forged access token therefore does not become a session. A substituted access token paired with an `id_token` whose unsigned payload repeats the pending nonce would. The token endpoint is the configured issuer, fetched server-side with redirects disabled. On this drop that issuer is HTTP on loopback (`sslRequired` is `none` in the realm). That substitution is a local-network or local-process problem today. It is a blocking defect for any identity provider that is not that loopback Keycloak.

**`tenant_id` in the token is not a ceiling.** After a real token is accepted, the session’s tenant id is whatever was stored in the cookie. The API authorizes `(X-Tenant-ID, sub)` against `tenant_memberships` and does not compare the header to a `tenant_id` claim. A subject who is a member of two tenants can use either. A subject who is not a member receives 403. That matches the threat model’s rule that the client tenant id is not proof of membership. It does not pin the session to the attribute Keycloak put on the token.

**End session is unverified.** `writeSession` sets `Path=/` and, in production, `Secure`. `clearSession` calls `cookies().delete` with the name only. The OIDC pending cookie is cleared with `Path=/callback` and `maxAge: 0`, and that clear does not repeat `Secure`. Next.js 15.5.4 forwards `delete` without adding those attributes. `node_modules` is not installed here, and no browser logout was run, so this review does not claim the cookie survives. It also does not claim that “End session” revokes the Keycloak session or the access token. The realm access-token lifetime is 900 seconds. The cookie `maxAge` is eight hours. A pasted token can outlive a failed cookie clear up to its own `exp`.

**Host-relative redirects.** Login and callback build `Location` with `new URL(path, request.url)`. The path is fixed (`/`, `/properties`, or the configured issuer). An attacker-controlled `Host` or forwarded host would make that location point at the attacker’s origin. The session cookie is host-only, so that redirect does not send the cookie to the other origin. There is no proxy in this drop. Treat an allowlisted public origin as required before a proxy is added.

**Delegated write versus property read (remediated on main).** Migration `011_write_grant_pages.sql` defines `actor_has_live_write_grant` and extends `property_private_read` so a live write grant can SELECT that property. Creator-only rules remain on share and further delegation. Confirm with current-head Active database security runs; do not reopen this as an open Gate 0 blocker without re-testing.

**Session and transport gaps the threat model already leaves open.** No refresh, no server-side revocation list, no MFA freshness beyond `amr` on the token, no immutable audit sink, no document scanning or encryption, no CSP, no HSTS. The runtime audit table is append-only for `oydp_app` and remains writable by a privileged database role. Keycloak HTTP and `hostname-strict=false` are limited by the Compose port binding. Importing that realm on a host that is not loopback would remove the limit. The pasted-token form remains available whenever the page renders.

**CI does not currently prove this branch.** Until a pull request runs `API smoke` and `Database security`, the new migration and the `otp` MFA change have no recorded result from those workflows.

## Secrets

No live credential was found in the reviewed diff, the realm import, or `.env.example`. Placeholders are labeled as local and replaceable. Compose requires `POSTGRES_PASSWORD` and `KEYCLOAK_ADMIN_PASSWORD` from the environment. The web client is public and PKCE-based, so the realm file correctly has no client secret. This search is not a complete secret scan of git history.

## Verdict

Conditional pass.

Blocking findings: (1) unsigned session cookie carrying the raw access token to a caller-chosen API base, and (2) the web dev server not bound to loopback while that behavior exists. Either one stops this gate as soon as the web process is reachable beyond the operator.

## Finding 1 resolution — 2026-11-04

The review above is unchanged. This addendum records the working-tree change on `feat/launch-1-drop-1` at `95465978ca13877ec166a53c73bf8030b4a3642b`. It is not committed.

The session cookie is now AES-256-GCM with a random 12-byte IV, the associated data `oydp-session`, and a 32-byte key from `SESSION_KEY` (base64url, not committed). The sealed payload is version, tenant, access token, and expiry. There is no fallback to the unsigned base64 cookie. A modified, expired, wrongly keyed, or origin-carrying payload is rejected. The OIDC pending cookie uses the same key and the associated data `oydp-oidc`. Cookies stay `HttpOnly`, `SameSite=Lax`, path-scoped, and `Secure` when `NODE_ENV=production`.

`callPropertyApi` reads `PROPERTY_API_BASE` on each call. A form field, cookie, query, or sealed payload cannot select another origin. The configured origin must be HTTPS, except `http` on `localhost` or `127.0.0.1`, and it cannot carry credentials, a path, a query, or a fragment. Redirect responses are rejected before a bearer token is followed. The connect form no longer has an API-origin field.

The callback verifies the ID token (RS256, issuer, client audience, expiry, nonce, type `JWT`) and the access token (RS256, issuer, `OIDC_AUDIENCE`, expiry, type `at+jwt`) against `OIDC_JWKS_URL`. It ignores `jku` and `x5u`. `tenant_id` is read only after that check, and the access token is still sent to `GET /v1/properties?limit=1` so the API verifier runs. PKCE, state, and nonce remain. Any failed check redirects home and does not write a session.

`apps/web` `npm test` then passed 13, failed 0, skipped 0. The previous `contract.mjs` at HEAD accepts the unsigned origin-carrying cookie and a caller-supplied origin; the new tests reject both. Typecheck, production build, and `npm audit` (0 vulnerabilities) passed. Active API tests passed 171 with 0 skipped. Reference tests passed 87 plus 13 subtests. OpenAPI `--check` matched. Keycloak and a browser login were not run. Finding 2 was already addressed by the `127.0.0.1` bind and was not reopened.

The sealed cookie still contains the access token until its own expiry. There is no server-side revocation list. Losing `SESSION_KEY` exposes every sealed cookie. This addendum does not make the gate a production approval or an independent audit.
