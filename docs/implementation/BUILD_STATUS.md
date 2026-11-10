# Build status

Truthful engineering status for the active modular monolith. Labels use only: planned, UI prototype, static mockup, placeholder, generated source, executable implementation, integration-tested, production-hardened, independently reviewed.

Base inspected: `origin/main` @ `887cc871a2a8bf03515a7f7c14218bf0a6f27dcb` (PR #16). Hardening branch: `feat/mfa-freshness-hardening`.

| Surface | Label | Notes |
| --- | --- | --- |
| Active Property Identity API (`apps/api`) | executable implementation / integration-tested (partial) | Private create/read/share, claims, corrections, write grants, evidence, documents quarantine, diligence, export consent |
| Root `oydp/` + `migrations/` | frozen reference | Separately tested PR #1 backend; not the evolving authority |
| AuthN JWKS / RS256 / at+jwt | executable implementation | Loopback HTTP gated by `OYDP_OIDC_DEV_HTTP` |
| MFA freshness (`auth_time`) | executable implementation | Default max age 900s; live IdP enrollment NOT VERIFIED |
| Tenant RLS + membership | integration-tested (CI history) | Runtime role must not migrate/admin |
| Encrypted documents + scan gate | executable implementation | Production malware scanner BLOCKED |
| Audit outbox / ledger | executable implementation | Not an external immutable archive |
| `apps/web` workspace | executable implementation (partial) | Authenticated property UI; browser E2E / live provider still open |
| Engines E02–E13 (except bounded E03 diligence) | planned | See ENGINE_REGISTER |

## This increment

Implemented configurable MFA freshness and optional ACR allowlisting in `apps/api/app/auth.py`, Keycloak `auth_time` mapper, DevOidc `auth_time`, tautology removal, and documentation updates. See `SECURITY_FINDINGS.md` and the feature PR verification report.
