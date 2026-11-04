# Launch 1, drop 1 — private desk

This is a local, pre-alpha workspace. It does not verify title, speak for a government office, or accept real client papers. Document upload, paid plans, and a public server are later drops.

## What this drop adds

- Local Keycloak realm `oydp` with a required one-time code and PKCE sign-in for the workspace.
- The API accepts `otp` or `mfa` in the access token `amr` claim. Issuer and JWKS URLs may use `http` only for `localhost` or `127.0.0.1`.
- `PATCH /v1/properties/{id}` corrects the label and jurisdiction. The previous values stay in `property_corrections` and an audit row.
- The owner can delegate writing to a same-tenant editor for at most 30 days. A delegated writer can correct and append unverified claims. A writer cannot share, revoke, or delegate further.
- The workspace shows a private-record notice on every screen, plus correction and writer forms.

## Local setup

1. Copy `.env.example` to `.env`. Replace every password with a different long random value.
2. Turn on Windows device encryption before any real file is stored.
3. Start the database and identity provider: `docker compose up -d db identity`.
4. Apply migrations and the runtime role with `MIGRATION_DATABASE_URL` pointing at the owner role, then start the API with `DATABASE_URL` pointing at `oydp_app`. See `docs/implementation/DATABASE_FOUNDATION.md`.
5. Set the API environment to the local issuer in `.env.example`. The `oydp-web` client sets the access-token header type to `at+jwt`. Enrollment, the required one-time code, and the auth-test record are in [the identity gate](IDENTITY_GATE.md).
6. In the Keycloak admin console at `http://127.0.0.1:8080`, realm `oydp`, create a user. Add attribute `tenant_id` with the membership UUID. The user configures an authenticator app on first sign-in.
7. Insert that subject into `tenant_memberships` as `owner` or `editor` through the database owner role. The client cannot choose its role.
8. For the web app, set `OIDC_CLIENT_ID=oydp-web`, `OIDC_REDIRECT_URI=http://127.0.0.1:3000/callback`, and `PROPERTY_API_BASE=http://127.0.0.1:8000`. Run `npm run dev` from `apps/web` and open `http://127.0.0.1:3000`.

The pasted-token form remains for tests and for an operator who already holds an access token. A missing or non-UUID `tenant_id` claim stops sign-in before a session cookie is stored.

## Security limits

Keycloak is bound to `127.0.0.1` and its realm allows HTTP because this drop runs on one computer. Do not expose port 8080. The correction and grant functions are `SECURITY DEFINER` with a fixed search path and no public execute grant. The runtime role cannot insert grants or correction rows directly. An administrator who owns this computer can still read an unencrypted disk. This drop is not an independent audit.
