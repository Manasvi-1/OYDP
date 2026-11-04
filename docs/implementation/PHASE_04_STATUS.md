# Phase 04 — current implementation status

Updated 4 November 2026. OYDP remains pre-alpha; this is a backend and workspace increment, not the completed 13-engine product.

## Implemented in the active apps/api service

- Configured JWKS and RS256 access-token signature/type/issuer/audience/expiry validation.
- Loopback HTTP issuer/JWKS only when `OYDP_OIDC_DEV_HTTP=1` (`endpoint_allowed` enforced in `verified_claims`).
- Trusted tenant membership checks with restricted runtime role and transaction-local forced RLS.
- Creator-private property create/read, issuer-asserted MFA for creation and sharing changes.
- Expiring same-tenant read grants, creator-only grant/revoke, idempotent atomic access audit.
- Write delegation, audited corrections, attributed unverified claims, cursor pagination.
- Document quarantine with AES-GCM (`DOCUMENT_STORAGE_KEY`); scanner adapter still absent (`None`).
- Trusted evidence identifiers, sources, reviews, consent-gated export; audit ledger and outbox.
- Diligence requests and notes (API 0.8.0).
- Checksum migrations `infra/db/001`–`014`, populated upgrade attribution and fail-closed unknown creators.
- Native PostgreSQL tests, dependency hash lock/audit and CI artifacts.

PR #1 remains a frozen compatibility/reference implementation under `oydp/` + root `migrations/`. It is not mounted into the active service and has no automatic data synchronization. See PR1_RECONCILIATION.md.

## Verification

Historical native CI for discovery/claims (`68f2875`): 115 active tests and 87 reference tests + 13 subtests, zero skips. Latest-head checks on each feature PR remain mandatory. See VERIFICATION_REGISTER.md for the consolidation sprint results once recorded.

## Next work

Production identity-provider selection and MFA freshness; real malware scanner adapter and quarantine state productization; independently delivered immutable audit archive; evidence identifier supersession and source conflict handling; broader workspace journeys. Independent human/security/legal review and production approval remain pending. No public deployment performed.

## Diligence requests

API 0.8.0 lets a creator open and close a request and lets a current reader add a note while it is open. See DILIGENCE_REQUESTS.md. This is not a transaction or legal workflow.

## Audit outbox

API 0.7.0+ enqueues one outbox row with each audit event and can append those identifiers to a local JSONL file. Delivered rows cannot be edited. See AUDIT_OUTBOX.md. An independent immutable sink is not included.

## Private documents and evidence lineage

Canonical document quarantine is migration `010`. Canonical identifiers, sources, reviews, and consent are migration `012`. The parallel `008` and `009` files from other pull requests were not applied, because those version numbers and table names already exist.

## Authenticated workspace

`apps/web` is a pre-alpha Next.js workspace for the authenticated property journey: authorization-code sign-in, paginated private discovery, property detail, claims, read access, and related flows. The access token stays in an encrypted httpOnly cookie and is sent only by the server. Loopback HTTP is accepted by the API only when `OYDP_OIDC_DEV_HTTP=1`. That process is a development issuer path, not a selected production provider. See WEB_UI.md. Current-head CI, including the browser journey where present, is the acceptance evidence.

## API 0.4.0 discovery/claim increment

Adds paginated private property discovery and attributed immutable user claims, fixed unverified status, claim-linked atomic audit, strict scoped cursors, exported active OpenAPI checks and commit-before-success handling. See DISCOVERY_CLAIMS.md. Reviewed implementation `68f2875` passed 115 active tests and 87 reference tests + 13 subtests in native CI, zero skips. Latest-head checks remain mandatory before merge. Live production identity-provider integration remains pending.
