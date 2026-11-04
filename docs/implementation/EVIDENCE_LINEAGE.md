# Evidence lineage — API 0.5.0

The parallel branch's `008_evidence_lineage.sql` was not added. Migrations `008` through `012` on main already own those version numbers, and `012_trusted_evidence.sql` is the canonical identifier and source schema. The notes below describe the branch that was merged for history. They are not a second set of tables.

## What it stores

- `evidence_sources` are notes attached to one property: `user_supplied`, `professional_note`, or `published_reference`, plus an optional locator. A class is a label the member chose. It is not a licence, a portal integration, or an official extract.
- `property_identifiers` keep history for `local_label`, `survey_number`, `khata`, and `municipal_reference`. One current row exists per property and scheme. A second value without `supersede: true` returns 409 and does not echo either value. Supersede stamps the previous row and appends the new one. History stays readable. These values are not verified survey or municipal records.
- Evidence assertions accept `user_claim` (`review_status=unreviewed`) or `professional_review` (`review_status=recorded`, and a source reference is required). `recorded` means the note was stored. It is not an approval. `official_observation` cannot be inserted by the runtime role. A source link must belong to the same property.

Reads follow the existing property rule: creator or current read grant. Writes require the creator, an owner or editor membership, and an MFA access token. Each write adds an audit row in the same transaction. A failed audit insert rolls the business row back.

## Rollback

No down migration is provided. Application code from 0.4.0 can still serve the older routes after 008 is applied; it will not write the new event types. Keep the new tables and history. Re-provision the runtime role when moving forward so `oydp_app` receives select/insert on the new tables and update only of `property_identifiers.superseded_at`.
