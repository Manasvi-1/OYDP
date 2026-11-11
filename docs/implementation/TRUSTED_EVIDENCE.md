# Trusted evidence — API 0.7.0

E01 stays partial. This slice adds versioned identifiers, a rights-unknown source registry, professional reviews that are not title, optional live source citations on unverified user claims (`015`), optional document↔claim/source attribution (`016`), optional document↔identifier attribution and export packet refs (`017`), optional review↔claim citation (`018`), optional review↔document/identifier citation (`019_review_document_identifier_attribution.sql`), creator consent for one export purpose, and an append-only database ledger. Attribution never changes claim verification, identifier status, review `title_effect`, or scan state. It does not verify title, speak for a government office, value a property, or approve a development. E02–E13 are not implemented.

Maturity of this slice: executable implementation, covered by the active API tests and the PostgreSQL integration tests. It is not production-hardened, not independently reviewed, and not a production approval.

## What runs

Migration `infra/db/012_trusted_evidence.sql` adds:

- `property_identifiers`. Schemes are `internal`, `survey`, `municipal`, and `khata`. The first value is current version 1. The same value is idempotent. A different value requires `supersede` or `conflict`. Supersede keeps one current row and retains history. Conflict leaves the previous current row in place.
- `evidence_sources`. `rights_status` is constrained to `unknown`. The client cannot set it. Withdrawal is recorded, not deleted.
- `professional_reviews`. Disposition is `recorded` or `abstained`. The API adds `title_effect: none`. A review does not update `property_claims.verification_status`.
- `property_consents`. The only purpose is `passport_export`. Only the property creator, while that creator's membership is `owner` or `editor`, can grant or revoke it.
- `audit_ledger`. Each insert into `property_audit_events` or `tenant_audit_events` is copied in the same transaction. A ledger insert must match that outbox row. Update, delete, and truncate are rejected.

`scripts/migrate.py` grants `oydp_app` select on those tables and execute on `record_property_identifier`, `register_evidence_source`, `withdraw_evidence_source`, `record_professional_review`, `record_property_claim`, `attribute_property_document`, `record_property_consent`, `revoke_property_consent`, and `authorize_property_export`. Claim rows are no longer directly insertable by the runtime role. Document attribution columns are not updatable by the runtime role except through `attribute_property_document`. It does not grant insert, update, or delete on trusted-evidence tables, and it does not grant `actor_can_edit_property` or the ledger trigger functions. The runtime role remains `NOBYPASSRLS`. Row security stays forced.

The active API in `apps/api/app/main.py` is version 0.16.0 (evidence conflict signals + export cited sources + runtime audit/source gates). Routes call those SQL functions with the existing authorized database session and, for writes and export, MFA. `GET /v1/properties/{id}/evidence-graph` and `GET /v1/properties/{id}/evidence-conflicts` are read-only under the same property visibility rule as claim/document/review lists; they do not require MFA and never assert title or adjudicate conflicts. SQL errors are mapped from an allowlist. `P0002` becomes 404. Missing consent becomes 403 `Export consent required`. A withdrawn or unknown source becomes 422 `Source is withdrawn`. Invalid document or review attribution (including non-current/foreign identifiers, foreign claims, or foreign documents) becomes 422 `Invalid attribution`. A changed identifier without a resolution becomes 422 `Identifier resolution required`. Other database failures stay a generic 503. Responses do not include SQL, tokens, or ciphertext. Claims remain `user_claim` / `unverified` even when cited by a document or review.

`POST /v1/properties/{id}/exports` calls `authorize_property_export` before reading the packet. The packet contains the caller's visible claims, still unverified, identifiers, reviews with `title_effect` none, document metadata including optional `claim_id`, `source_id`, and `identifier_id` attribution refs, and the cited `sources` rows (rights remain `unknown`). It sets `title_verified` false and states that it is not a title certificate. Document ciphertext is not selected.

`GET /v1/properties/{id}/documents` returns quarantined metadata. `GET /v1/properties/{id}/audit` returns `event_type`, `actor_subject`, `recorded_at`, and `delivered_at` for delivered ledger rows of that property.

The workspace in `apps/web` can upload a quarantined file, record an identifier, record a review, register or withdraw a source, grant or revoke export consent, and download the packet only after the API allows it. A document download link is shown only when `scan_state` is `pass`. The upload is limited to 1 MB and to PDF, PNG, or JPEG; the API checks the bytes again. The session still does not accept a caller-chosen API origin. `dev` and `start` stay bound to `127.0.0.1`.

## What this is not

- A bundled malware scanner. `get_document_scanner` returns none unless an operator configures one. Absent, failing, and unexpected scanner results stay fail closed.
- An external write-once audit store. The ledger is a PostgreSQL table. A database superuser can disable its triggers.
- Browser end-to-end coverage. The workspace has contract tests, typecheck, and a production build. A signed-in browser journey was not treated as done.
- Title verification, government affiliation, guaranteed valuation, or development approval.
- Completion of E02–E13, or of the rest of the E01 evidence graph.
