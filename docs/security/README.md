# Security engineering policy

OYDP handles potentially sensitive property and identity information. Security claims require executable evidence.

## Mandatory controls
1. OIDC verification: issuer, audience, signature, expiry, key rotation and MFA for sensitive roles.
2. Server-resolved tenant membership and object-specific permissions.
3. Non-owner database runtime role, FORCE RLS, and two-tenant negative integration tests.
4. Encryption in transit and at rest, scoped object storage and malware quarantine.
5. Consent records, revocable grants, purpose limitation and retention/deletion workflows.
6. Immutable or independently integrity-protected audit events.
7. Secure CI, dependency review, secrets scanning and reproducible deployments.
8. Observability without deed text, credentials or sensitive personal data.
9. Independent legal and privacy review before processing production customer records.

## Current state
The repository has preliminary policies and fail-closed endpoints. These controls have not been fully implemented or externally audited. Never use the foundation to process real deeds or customer identities.

Report suspected vulnerabilities privately to the repository owner; do not disclose exploit details in public issues.
