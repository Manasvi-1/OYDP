# Security findings register

Engineering self-review notes. Passing automated tests are not an independent audit or production certification.

Updated from the MFA freshness hardening increment on branch `feat/mfa-freshness-hardening` (base `887cc87`).

| ID | Severity | Area | Status | Finding | Evidence / remediation |
| --- | --- | --- | --- | --- | --- |
| SF-001 | High | AuthN / MFA | Fixed (code) | High-risk routes treated `amr` containing `mfa`/`otp` as sufficient MFA without freshness | `require_mfa` now requires integer `auth_time` within `OYDP_MFA_MAX_AGE_SECONDS` (default 900) unless explicitly set to `0`; tests cover missing/stale/future/malformed claims |
| SF-002 | Medium | AuthN / IdP | Mitigated (config) | Local Keycloak access tokens previously lacked an `auth_time` mapper | Realm mapper `auth-time` maps session note `AUTH_TIME`; live enrollment still NOT VERIFIED on this machine |
| SF-003 | Medium | Documents | Blocked | No production malware scanner is bundled; `get_document_scanner()` returns `None` | Fail-closed quarantine/download gates remain; production scanner labeled BLOCKED until infra provides an adapter |
| SF-004 | Medium | Audit | Open | `audit_ledger` / outbox are append-oriented application controls, not an external immutable archive | Documented in ROADMAP / AUDIT_OUTBOX; superuser can still disable triggers |
| SF-005 | Low | Tests | Fixed | `test_canonical_authority.py` contained tautology `assert 'app' in sys.modules or True` | Replaced with import-boundary assertions for `app.main` vs `oydp` |
| SF-006 | High | AuthN | Unverified | Live production IdP enrollment, token revocation, and session kill on membership change | Still pending; unit/dev-issuer tests do not prove production IdP behavior |
| SF-007 | Medium | Tenant isolation | Partially verified | Cross-tenant IDOR denials exist in native CI history; this increment did not expand share/document/export negative matrix | Prior integration coverage remains the evidence; re-run native DB CI on the feature PR |

## Explicit non-claims

- No governmental affiliation, guaranteed title, valuation, or returns.
- Automated green tests do not mean production-hardened or independently reviewed.
- Document scanning remains BLOCKED for production malware detection until a real scanner adapter is installed and verified.
