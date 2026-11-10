# Initial threat model — first vertical slice

This is an engineering draft; it is not an independent security assessment.

| Boundary/threat | Required control | Evidence now |
|---|---|---|
| Client forges identity, membership or MFA | Verified OIDC identity; resolve tenant membership server-side | Pinned RS256 token checks and MFA gate with configurable `auth_time` freshness tested; production rejects freshness-disable without explicit loopback/dev; live managed OIDC enrollment still BLOCKED locally |
| User guesses another tenant/property ID | Per-object policy plus database RLS and composite integrity | API and repository grant denials plus forced tenant RLS; expanded cross-tenant IDOR matrix awaiting native PG CI; local PG skipped when Docker/engine unavailable |
| Collaborator retains revoked access | Fetch current grants each access; terminate stale sessions where required; revocation-aware delivery | Creator-managed revocation and native concurrent membership/grant/shared-reader checks passed; file delivery pending |
| Collaborator escalates or reshares access | Creator-only management, bounded expiry, active same-tenant recipients, audited mutations | Negative tests and audited SECURITY DEFINER function; see PROPERTY_ACCESS.md for trust assumptions and non-cascading revocation |
| Property read permission leaks all deeds | Explicit resource grant and scanning gate | Unit policy tested |
| Malicious file exploits preview or scanner | Quarantine, byte caps, MIME detection, sandbox scanner, no active-content execution | No file service implemented |
| Duplicate property creates false title conclusion | Candidate identity, unresolved matches, attributed assertions, human correction | Candidate creation and unverified claims persisted; deduplication and correction workflow pending |
| Reviewer impersonation | Verify professional credentials separately from authentication | Not implemented |
| AI prompt injection changes access | Policy outside AI; untrusted document content; scoped retrieval | No AI implementation |
| Partial write loses audit | Commit mutation and outbox atomically; independent immutable delivery | Transactional outbox and rollback tested; independent immutable sink pending |
| Logs or exports disclose documents | Redacted telemetry, scoped exports, retention/deletion/legal-hold handling | Not implemented |

## Trust assumptions and limits

Dataclasses are internal contracts, not a hostile-input validation boundary. Application request models must validate UUIDs, lengths, enum values and timezone-aware dates. The grant repository must prevent unauthorized creation and resolve concurrent revocation consistently. Treat scan state as trusted only when persisted by an authenticated scanner worker against the exact object/version digest. Consent needs purpose, permitted fields, legal basis and lifecycle beyond this initial property/document grant model.

No production release is permitted on the strength of these unit tests. The blueprint's eight gates remain open: functional, data/legal, security, privacy, AI/calculation, operations, commercial and governance.
