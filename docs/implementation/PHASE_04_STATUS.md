# Phase 04 — current implementation status

Updated 25 October 2026. OYDP remains pre-alpha; this is a backend increment, not the completed 13-engine product.

## Implemented in the active apps/api service

- Configured HTTPS JWKS and RS256 access-token signature/type/issuer/audience/expiry validation.
- Trusted tenant membership checks with restricted runtime role and transaction-local forced RLS.
- Creator-private property create/read, issuer-asserted MFA for creation and sharing changes.
- Expiring same-tenant read grants, creator-only grant/revoke, idempotent atomic access audit.
- Checksum migrations, populated upgrade attribution and fail-closed unknown creators.
- Native PostgreSQL tests, dependency hash lock/audit and CI artifacts.

PR #1 has been reconciled and merged, preserving its native-tested root-package grant/claim backend as a separate compatibility/reference implementation. It is not mounted into the active service and has no automatic data synchronization. See PR1_RECONCILIATION.md.

## Verification

PR #1 reconciliation: 87 native PostGIS tests + 13 subtests and 48 active tests passed without skips. First private-access implementation `71ffa34`: 71 active tests and 87 reference tests + 13 subtests passed without skips. Final reviewed implementation `21d9bc0` tightened evidence writes after creator role downgrade and passed 72 active tests plus 87 reference tests and 13 subtests, with no skips. See VERIFICATION_REGISTER.md and the PR for exact commit/run links.

## Next work

Property write delegation/correction workflows, production identity-provider selection and MFA freshness, scan/quarantine/encryption for documents, independently delivered audit history and remaining engine journeys. Independent human/security/legal review and production approval remain pending. No public deployment performed.

## Diligence requests

API 0.8.0 lets a creator open and close a request and lets a current reader add a note while it is open. See DILIGENCE_REQUESTS.md. This is not a transaction or legal workflow.

## Audit outbox

API 0.7.0 enqueues one outbox row with each audit event and can append those identifiers to a local JSONL file. Delivered rows cannot be edited. See AUDIT_OUTBOX.md. An independent immutable sink is not included.

## Private documents

API 0.6.0 stores creator-only document metadata and encrypted PDF, PNG, or JPEG bytes. Active-content and EICAR uploads are recorded as rejected and are not stored. See PRIVATE_DOCUMENTS.md. A certified malware scanner is not included.

## Evidence lineage

API 0.5.0 adds migration 008 and creator/MFA routes for source notes, versioned identifiers, and evidence assertions. Runtime insert of `official_observation` is denied. See EVIDENCE_LINEAGE.md. This does not complete the evidence graph or document storage.

## Authenticated workspace

`apps/web` is a pre-alpha Next.js workspace for the API 0.4.0 journey: authorization-code sign-in, paginated private discovery, property detail, and unverified claim recording. The access token stays in an encrypted httpOnly cookie and is sent only by the server. Loopback HTTP is accepted by the API only when `OYDP_OIDC_DEV_HTTP=1`, for `tools/dev_oidc.py`. That process is a development issuer, not an authenticator and not a selected production provider. See WEB_UI.md. Current-head CI, including the browser journey, is the acceptance evidence.

## API 0.4.0 discovery/claim increment

Adds paginated private property discovery and attributed immutable user claims, fixed unverified status, claim-linked atomic audit, strict scoped cursors, exported active OpenAPI checks and commit-before-success handling. See DISCOVERY_CLAIMS.md. Initial local unit/API tests: 43 passed. Reviewed implementation `68f2875` passed 115 active tests and 87 reference tests + 13 subtests in native CI, zero skips. Latest-head checks remain mandatory before merge. UI and live identity-provider integration remain pending.
