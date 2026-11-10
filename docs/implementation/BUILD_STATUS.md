# Build status

Truthful engineering status for the active modular monolith. Labels use only: planned, UI prototype, static mockup, placeholder, generated source, executable implementation, integration-tested, production-hardened, independently reviewed.

Base inspected: PR #17 head `f5cf84e35a469ed918172fe55dbe3240bca69f8d` (`feat/mfa-freshness-hardening`, OPEN, CI green). This increment branch: `security/live-keycloak-and-tenant-idor`.

| Surface | Label | Notes |
| --- | --- | --- |
| Active Property Identity API (`apps/api`) | executable implementation / integration-tested (partial) | Private create/read/share, claims, corrections, write grants, evidence, documents quarantine, diligence, export consent |
| Root `oydp/` + `migrations/` | frozen reference | Separately tested PR #1 backend; not the evolving authority |
| AuthN JWKS / RS256 / at+jwt | executable implementation | Loopback HTTP gated by `OYDP_OIDC_DEV_HTTP` |
| MFA freshness (`auth_time`) | executable implementation | Default max age 900s; zero rejected outside loopback/dev; live IdP enrollment BLOCKED locally |
| Tenant RLS + membership | integration-tested (CI history) + expanded IDOR matrix (local PG skipped) | Runtime role must not migrate/admin |
| Encrypted documents + scan gate | executable implementation | Production malware scanner BLOCKED |
| Audit outbox / ledger | executable implementation | Not an external immutable archive |
| `apps/web` workspace | executable implementation (partial) | Session/proxy tenant isolation unit tests; browser E2E / live provider still open |
| Engines E02–E13 (except bounded E03 diligence) | planned | See ENGINE_REGISTER |

## This increment

Live Keycloak MFA verification attempted and marked BLOCKED (Docker engine unavailable). Production rejection of `OYDP_MFA_MAX_AGE_SECONDS=0` outside `OYDP_OIDC_DEV_HTTP=1`. Expanded cross-tenant IDOR integration matrix. Frontend session/proxy tenant isolation tests. Live claim inspection script. Documentation updates keep PR #17 MFA freshness conceptually separate.
