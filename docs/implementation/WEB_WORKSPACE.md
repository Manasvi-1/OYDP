# Authenticated property workspace

`apps/web` is the first Next.js journey for the active property API. It is pre-alpha and does not complete OYDP.

## What it does

- Accepts an operator-configured API base, tenant UUID, and an already issued access token.
- Can start a PKCE sign-in against a configured identity provider. The provider must put a UUID `tenant_id` on the access token.
- Stores that token in an httpOnly session cookie. The browser JavaScript does not receive it.
- Lists privately visible properties, creates a record, opens one record, corrects the label and jurisdiction, appends an unverified claim, and grants or revokes expiring read or write access.
- Shows a private-record notice on every screen. Claim statements stay text with the fixed unverified status.
- Rejects non-local `http` API bases, credentialed URLs, and redirects from the property service.

## What it does not do

- It does not refresh or revoke an identity-provider session. MFA is the `mfa` or `otp` method asserted by the access token.
- It does not upload documents or run the other engines.
- Passing `npm test` covers session, query, and sign-in URL construction. It is not a full browser journey and not production approval.

## Checks

From `apps/web`: `npm ci`, `npm test`, `npm run typecheck`, and `npm run build`. GitHub workflow `web workspace` runs those checks.
