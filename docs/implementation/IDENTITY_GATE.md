# Identity gate

Local development identity only. This is the loopback Keycloak realm the repository can start on one computer. It is not an enrolled production tenant, not a deployed identity provider, and not an independent security review.

No user, password, client secret, TOTP seed, or tenant UUID is stored in the repository. `.env` stays untracked. The example values in `.env.example` are placeholders.

## Configuration

| Piece | Role |
| --- | --- |
| `compose.yaml` service `identity` | Keycloak `26.4.2`, published only on `127.0.0.1:8080`, realm import from `infra/keycloak`, local `dev-file` database |
| `infra/keycloak/oydp-realm.json` | Realm `oydp`: public PKCE client `oydp-web`, bearer-only audience client `oydp-api` |
| `.env.example` | `OIDC_ISSUER`, `OIDC_AUDIENCE=oydp-api`, `OIDC_JWKS_URL`, and the local admin username. The admin password is supplied only in the untracked `.env` |

`oydp-web` sets client attribute `access.token.header.type.rfc9068=true`, so access tokens use JOSE header `typ=at+jwt`. The audience mapper adds `oydp-api` to the access token and not to the ID token. The AMR mapper puts the completed authenticator references on the access token. Password is reference `pwd`. The one-time code is reference `otp`. Each reference stays valid for 900 seconds, the same lifetime as the access token, so a normal code exchange still carries `otp`. Keycloak's default max age of 0 drops the reference when issuance crosses a one-second boundary.

The API verifier in `apps/api/app/auth.py` checks RS256, `typ=at+jwt`, `kid`, issuer, audience, subject, expiry, and issuance time. HTTP issuer and JWKS URLs are accepted only for `localhost` and `127.0.0.1`. Writes go through `require_mfa`, which accepts `otp` or `mfa` in `amr` and rejects every other method. There is no environment flag that skips verification.

## Enrollment

1. Copy `.env.example` to `.env`. Replace `KEYCLOAK_ADMIN_PASSWORD` and `POSTGRES_PASSWORD` with different long random values. Do not commit `.env`.
2. Start the provider with `docker compose up -d identity`. The admin password is read from `.env`. Do not publish port 8080.
3. Open `http://127.0.0.1:8080` and sign in to the `master` realm with `KEYCLOAK_ADMIN_USERNAME` (default `oydp-admin`).
4. In realm `oydp`, create one local user and set that user's password in the admin console. Self-registration and password reset are off. Do not put this user in the realm file.
5. Set the user's attribute `tenant_id` to a membership UUID that already exists in the local database. Do not invent a production tenant. The API does not authorize from this claim. `tenant_memberships` does.
6. On first sign-in the user must configure an authenticator app. The browser flow then requires the password and the one-time code. Direct access grants, implicit flow, and service accounts are off, so a password alone cannot mint an access token.
7. Copy the Keycloak user id into `tenant_memberships` as `owner` or `editor` using the database owner role. The client cannot choose the role.
8. Point the API at the issuer, audience, and JWKS URL in `.env.example`. For the workspace, set `OIDC_CLIENT_ID=oydp-web`, `OIDC_REDIRECT_URI=http://127.0.0.1:3000/callback`, and `PROPERTY_API_BASE=http://127.0.0.1:8000`.

A token whose `amr` claim lacks `otp` or `mfa` can still identify a subject for a read. It cannot perform a write.

## What this run did not do

Docker is not installed in this shell, so the Keycloak container was not started and no browser enrollment was performed. The realm file and the verifier tests are the evidence for this gate. A passing unit suite does not prove the imported realm issues a token.

This Windows Python is the embeddable build. `python311._pth` ignores `PYTHONPATH`, and `python -m venv` is unavailable. `python -m pip install --require-hashes -r apps/api/requirements.lock` stops because Windows `psycopg` pulls `tzdata`, which the lock does not pin. The installed set is the hash-checked lock with `--no-deps`, then `tzdata==2026.6` without a lock hash. Packages are in `Python311\Lib\site-packages`. `tzdata` is not a secret.

## Auth tests

Working directory: `C:\Users\WorkstationAdmin\OYDP`.

```text
python -c "import sys; sys.path.insert(0, r'apps/api'); import pytest; raise SystemExit(pytest.main(['-q','apps/api/tests/test_auth.py','-ra']))"
```

Result: **34 passed, 0 failed, 0 skipped**. Exit code 0. Elapsed 2.06s. Pytest 9.1.1.

On Linux CI the same file is `PYTHONPATH=apps/api:. python -m pytest -q apps/api/tests/test_auth.py`. That form was not executed here because this interpreter ignores `PYTHONPATH`.

The new negative cases are `test_expired_token_denied`, `test_wrong_audience_denied`, and `test_non_mfa_token_denied_for_writes`. An expired token and a token whose audience is `oydp-web` are rejected with 401 even when `amr` contains `otp`. A password-only token resolves the subject and is rejected with 403 on a write. Missing issuer, audience, or JWKS configuration returns 503. `test_local_realm_has_no_bypass_and_no_stored_users` rejects a realm that enables registration, direct grants, an optional one-time code, a stored user, or a credential.

## Maturity

Local provider configuration and verifier tests are in the working tree. A live provider was not enrolled on this machine. This is not production authentication, not a production tenant, and not an audit.
