# Authenticated property workspace

`apps/web` is the first Next.js journey for the active property API. It is pre-alpha and does not complete OYDP.

## What it does

- Uses `PROPERTY_API_BASE` as the only property-service origin. The connect form accepts a tenant UUID and an already issued access token. It does not accept an API origin.
- Can start a PKCE sign-in against a configured identity provider. The ID token is checked for signature, issuer, audience, expiry, and nonce. The access token is checked the same way, including `at+jwt`, and is then probed through the property API. The provider must put a UUID `tenant_id` on the access token.
- Stores the tenant and access token in an AES-256-GCM cookie sealed with `SESSION_KEY`. The cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` when `NODE_ENV=production`. Browser JavaScript does not receive the token. An unsigned cookie is rejected.
- Generate `SESSION_KEY` with `node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"`. Do not commit it.
- Lists privately visible properties, creates a record, opens one record, corrects the label and jurisdiction, appends an unverified claim, and grants or revokes expiring read or write access.
- Shows a private-record notice on every screen. Claim statements stay text with the fixed unverified status.
- Requires HTTPS for the API origin except `http` on `localhost` or `127.0.0.1`. Rejects credentials, a path, a query, a fragment, and a redirect from the property service.

## What it does not do

- It does not refresh or revoke an identity-provider session. MFA is the `mfa` or `otp` method asserted by the access token.
- It does not upload documents or run the other engines.
- Passing `npm test` covers the sealed session, API-origin checks, and local token verification. It is not a browser journey, a live Keycloak login, or production approval.

## Checks

From `apps/web`: `npm ci`, `npm test`, `npm run typecheck`, and `npm run build`. GitHub workflow `web workspace` runs those checks.
