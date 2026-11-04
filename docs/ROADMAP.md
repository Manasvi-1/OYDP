# Engineering roadmap

## Source of truth
Controlled master blueprint (2026-10-16), 13-engine product specification, and gated development roadmap. This document tracks proposed implementation, not proof of completion.

## Milestone 0 — Foundation and verifiable access control
- [x] Initial FastAPI skeleton and fail-closed property routes committed
- [x] Initial PostgreSQL RLS policies committed
- [x] API smoke tests authored
- [x] Run backend suites in CI and capture results (PR #1 and PR #2)
- [ ] Provision migration/runtime roles; apply migrations to a clean PostGIS instance
- [x] Implement and test JWT signature, issuer, audience and expiry (live provider onboarding pending)
- [x] Resolve tenant membership from trusted database state
- [x] Cross-tenant integration tests with distinct tenant fixtures
- [x] Private property create/read and read-sharing API with tested contract
- [x] Paginated property discovery and attributed unverified claims (API 0.4.0; native CI 115 tests)
- [x] Property update/write delegation and correction workflows
- [ ] Next.js authenticated property workspace is in `apps/web` and calls the active API. Browser end-to-end coverage and live provider enrollment are still open

## Milestone 1 — Trusted evidence
- [x] Versioned property identifiers, source registry, and conflict resolution. `rights_status` stays unknown. API 0.7.0.
- [x] Professional reviews are recorded or abstained. A review does not change claim verification and has no title effect.
- [x] Property and tenant audit rows are copied into `audit_ledger` in the same transaction. The ledger rejects update, delete, truncate, and an insert that does not match an outbox row. This is not an external write-once store. A database superuser can disable triggers.
- [ ] Quarantined, encrypted document storage is in the API. No malware scanner is bundled. A file stays closed until a configured scanner marks it clean.
- [x] Creator consent for `passport_export` can be granted and revoked. Export requires that live consent. Read and write grants remain separate.

## Milestone 2 — Collaborative property lifecycle
- [ ] E03 Transaction & Legal Workspace
- [ ] E04 Living Property Passport
- [ ] E05 Ownership Action Engine
- [ ] E02 Source-grounded AI Advisor
- [ ] E06 Real Estate Academy

## Milestone 3 — Spatial and financial decision support
- [ ] E07 GIS with CRS/source attribution
- [ ] E08 Licensed comparable valuation
- [ ] E09 Concept layout studio
- [ ] E10 Reproducible feasibility calculators
- [ ] E12 Temporal spatial twin

## Milestone 4 — Network and integrations
- [ ] E11 Consent-based marketplace and moderation
- [ ] E13 Institutional API with scoped grants and revocation

## Milestone 5 — General availability gates
- [ ] All 13 real end-to-end workflows
- [ ] Legal and data rights approvals
- [ ] External security review and authorization tests
- [ ] Privacy, deletion, export and consent tests
- [ ] AI, GIS and financial calculation verification
- [ ] Restore drills, SLOs and operational readiness
- [ ] Paid pilot validation and unit economics
- [ ] Signed product, engineering, security and legal release decision

Do not mark an item complete solely because a design document or placeholder exists.
