# Initial threat model — first vertical slice

This is an engineering draft; it is not an independent security assessment.

| Boundary/threat | Required control | Evidence now |
|---|---|---|
| Client forges identity, membership or MFA | Verified OIDC identity; resolve tenant membership server-side | Not implemented; policy requires trusted inputs |
| User guesses another tenant/property ID | Per-object policy plus database RLS and composite integrity | Unit policy denial tested; database/API pending |
| Previously invited reviewer retains access | Fetch current grants each access; terminate stale sessions where required; revocation-aware delivery | Revoked grant input tested; integration pending |
| Property read permission leaks all deeds | Explicit resource grant and scanning gate | Unit policy tested |
| Malicious file exploits preview or scanner | Quarantine, byte caps, MIME detection, sandbox scanner, no active-content execution | No file service implemented |
| Duplicate property creates false title conclusion | Candidate identity, unresolved matches, attributed assertions, human correction | Provenance type validation only |
| Reviewer impersonation | Verify professional credentials separately from authentication | Not implemented |
| AI prompt injection changes access | Policy outside AI; untrusted document content; scoped retrieval | No AI implementation |
| Partial write loses audit | Commit mutation and outbox atomically; independent immutable delivery | Not implemented |
| Logs or exports disclose documents | Redacted telemetry, scoped exports, retention/deletion/legal-hold handling | Not implemented |

## Trust assumptions and limits

Dataclasses are internal contracts, not a hostile-input validation boundary. Application request models must validate UUIDs, lengths, enum values and timezone-aware dates. The grant repository must prevent unauthorized creation and resolve concurrent revocation consistently. Treat scan state as trusted only when persisted by an authenticated scanner worker against the exact object/version digest. Consent needs purpose, permitted fields, legal basis and lifecycle beyond this initial property/document grant model.

No production release is permitted on the strength of these unit tests. The blueprint's eight gates remain open: functional, data/legal, security, privacy, AI/calculation, operations, commercial and governance.
