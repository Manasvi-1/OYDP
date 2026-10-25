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

This foundation is intentionally fail-closed. No production auth, official sources, or scanned documents are implemented.

## Current implementation clarification

JWT and tenant membership are implemented for the limited tenant-shared create/read API (PROPERTY_API.md). Route configuration alone is not release approval. Property-specific grants and external audit delivery remain required before private real-data workflows; evidence upload remains absent. The application audit table is append-only for the runtime role, not immune to privileged administrators. Dependencies are hash-locked and scanned in CI; independent review and release gates remain open.
