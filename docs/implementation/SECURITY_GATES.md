# Security gates — must pass before enabling any property routes

1. Authenticate with configured OIDC JWKS; enforce issuer, audience, signature, expiry, token type, and key rotation.
2. Resolve membership from trusted database state; client-supplied tenant IDs are not proof of membership.
3. Use a dedicated non-owner database role without BYPASSRLS; FORCE RLS on all tenant data tables.
4. Bind tenant scope transaction-locally and reset automatically on commit/rollback.
5. Test two tenant fixtures for read, list, create, update, delete and cross-tenant foreign key references.
6. Separate user claims from professional reviews and verified official observations.
7. Add audit outbox and immutable delivery before handling real user documents.
8. Keep evidence upload disabled until scanning, quarantine, encrypted storage and authorized download are operational.
9. Do not claim governmental verification, property ownership certification, or official API integrations.
10. Review CI and dependency scanning before merging to main.

## Current implementation clarification

The active apps/api service implements configured-JWKS JWT validation, database membership, creator-private property records, expiring read grants and revocations, signed-MFA-gated writes, attributed unverified claims, quarantined documents, and atomic audit writes. Native database tests exercise tenant and property authorization. A production identity provider has not been selected.

The workspace can keep an access token in an httpOnly session cookie. A pasted-token form remains for local use. The root oydp package is a separately tested reference backend; its functionality and test counts are not additional active service features.

The application audit table is append-only for the runtime role, not immune to privileged administrators. An external immutable audit sink, a certified malware scanner, independent security review, and production release acceptance remain open. No engine is complete.
