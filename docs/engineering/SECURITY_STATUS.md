# Security status

Engineering self-assessment. **Not** an independent audit or production certification.

Updated: 2026-11-11. Companion: `docs/implementation/SECURITY_FINDINGS.md`, `docs/THREAT_MODEL.md`.

## Control summary

| Control | State | Location |
| --- | --- | --- |
| OIDC RS256 `at+jwt`, iss/aud/exp/iat, reject crit/jku/x5u | Implemented + unit-tested | `apps/api/app/auth.py` |
| HTTPS JWKS/issuer; loopback HTTP only with `OYDP_OIDC_DEV_HTTP=1` | Implemented + unit-tested | `endpoint_allowed` |
| MFA `amr` ∩ {mfa,otp} | Implemented + unit/route-tested | `require_mfa` |
| MFA `auth_time` freshness (default 900s) | Implemented + unit/route-tested | `require_mfa` |
| SF-008: max-age 0 refused outside loopback | Implemented + unit/route-tested | `assert_mfa_configuration`, lifespan |
| Optional ACR allowlist | Implemented + unit-tested | `OYDP_MFA_ACR_VALUES` |
| Tenant membership FOR SHARE + RLS FORCE | Implemented; CI integration | `infra/db`, `authorized_db` |
| Cross-tenant IDOR matrix | Implemented; CI verified historically | `test_z_cross_tenant_idor.py` |
| Grant revoke/expiry | Implemented; CI | SECURITY DEFINER grants |
| Document encrypt + quarantine + content gate | Implemented; scanner BLOCKED | `documents.py`, `010` |
| Audit outbox/ledger append controls | Implemented; not external WORM | `013` |
| Web CSP / proxy origin checks | Implemented; web CI | `apps/web` |
| Secret scan light | Script present; 0 hits this session | `scripts/secret_scan_light.py` |

## Findings tracker (rollup)

| ID | Severity | Status |
| --- | --- | --- |
| SF-001 MFA without freshness | High | Fixed (code) |
| SF-002 Keycloak auth_time mapper | Medium | Mitigated config; live BLOCKED |
| SF-003 Malware scanner | Medium | BLOCKED |
| SF-004 External immutable audit | Medium | Open |
| SF-005 Tautology test | Low | Fixed |
| SF-006 Live IdP / session kill | High | BLOCKED / unverified |
| SF-007 IDOR matrix | Medium | Fixed / CI verified; local PG blocked here |
| SF-008 MFA max-age 0 prod | Medium | Fixed (code); restored onto interview branch |

## Session security work

- Restored SF-008 + IDOR file via merge from main.
- Added route-level MFA negatives (pwd-only, missing/stale `auth_time`, zero max-age → 503).
- Corrected threat-model file-service evidence row.
- Secret scan: 0 hits.

## Residual risk statement

Automated green tests do not prove production security. Live IdP, malware scanning, session revocation at the provider, privacy deletion, and independent review remain open. Do not ship GA on this evidence alone.
