# Authenticated property workspace

`apps/web` is the first Next.js journey for the active property API. It is pre-alpha and does not complete OYDP.

## What it does

- Accepts an operator-configured API base, tenant UUID, and an already issued access token.
- Stores that token in an httpOnly session cookie. The browser JavaScript does not receive it.
- Lists privately visible properties, creates a record, opens one record, appends an unverified claim, and grants or revokes expiring read access.
- Renders claim statements as text and keeps the fixed unverified status visible.
- Rejects non-local `http` API bases, credentialed URLs, and redirects from the property service.

## What it does not do

- It does not enroll, refresh, or revoke an identity provider. MFA is whatever the supplied access token already asserts.
- It does not upload documents, correct records, delegate writes, or run the other engines.
- Passing `npm test` covers session and query construction only. It is not browser end-to-end evidence and not production approval.

## Checks

From `apps/web`: `npm ci`, `npm test`, `npm run typecheck`, and `npm run build`. GitHub workflow `web workspace` runs those checks.
