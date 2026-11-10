# Security findings register

Engineering self-review notes. Passing automated tests are not an independent audit or production certification.

Updated from the live Keycloak + cross-tenant IDOR increment on branch `security/live-keycloak-and-tenant-idor` (base PR #17 head `f5cf84e`). PR #17 MFA freshness work remains conceptually separate.

| ID | Severity | Area | Status | Finding | Evidence / remediation |
| --- | --- | --- | --- | --- | --- |
| SF-001 | High | AuthN / MFA | Fixed (code) | High-risk routes treated `amr` containing `mfa`/`otp` as sufficient MFA without freshness | `require_mfa` requires integer `auth_time` within `OYDP_MFA_MAX_AGE_SECONDS` (default 900) unless explicitly set to `0` under `OYDP_OIDC_DEV_HTTP=1` |
| SF-002 | Medium | AuthN / IdP | Mitigated (config) / live BLOCKED | Local Keycloak access tokens previously lacked an `auth_time` mapper | Realm mapper present; live enrollment + claim emission BLOCKED on this machine (Docker daemon unavailable) |
| SF-003 | Medium | Documents | Blocked | No production malware scanner is bundled; `get_document_scanner()` returns `None` | Fail-closed quarantine/download gates remain |
| SF-004 | Medium | Audit | Open | `audit_ledger` / outbox are append-oriented application controls, not an external immutable archive | Superuser can still disable triggers |
| SF-005 | Low | Tests | Fixed | Canonical authority tautology | Replaced with import-boundary assertions |
| SF-006 | High | AuthN | Unverified / BLOCKED | Live production IdP enrollment, token revocation, and session kill on membership change | Live Keycloak verification script exits BLOCKED without a running provider |
| SF-007 | Medium | Tenant isolation | Partially verified (expanded matrix) | Prior cross-tenant gaps on grants/reviews/consent/export/scan/diligence/list | New `tests/integration/test_z_cross_tenant_idor.py` matrix; local native PG skipped (no Docker/Postgres); CI native DB job is the acceptance authority |
| SF-008 | Medium | AuthN / config | Fixed (code) | `OYDP_MFA_MAX_AGE_SECONDS=0` could disable freshness outside explicit loopback/dev | Startup `assert_mfa_configuration` and request-time checks reject zero unless `OYDP_OIDC_DEV_HTTP=1` |

## Explicit non-claims

- No governmental affiliation, guaranteed title, valuation, or returns.
- Automated green tests do not mean production-hardened or independently reviewed.
- Document scanning remains BLOCKED for production malware detection until a real scanner adapter is installed and verified.
- Synthetic JWTs are not evidence of live IdP integration.
