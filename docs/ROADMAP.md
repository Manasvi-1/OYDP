# Engineering roadmap

## Source of truth
Controlled master blueprint (2026-10-16), 13-engine product specification, and gated development roadmap. This document tracks proposed implementation, not proof of completion.

## Milestone 0 — Foundation and verifiable access control
- [x] Initial FastAPI skeleton and fail-closed property routes committed
- [x] Initial PostgreSQL RLS policies committed
- [x] API smoke tests authored
- [ ] Run tests in CI and capture results
- [ ] Provision migration/runtime roles; apply migrations to a clean PostGIS instance
- [ ] Verify OIDC token signature, issuer, audience and expiry
- [ ] Resolve tenant membership from trusted database state
- [ ] Cross-tenant integration tests with distinct tenant fixtures
- [ ] Create/read/update property API and OpenAPI client contract
- [ ] Next.js frontend for the first authenticated property journey

## Milestone 1 — Trusted evidence
- [ ] Versioned property identifiers, source registry and conflict resolution
- [ ] Evidence provenance assertions with professional review status
- [ ] Transactional audit outbox, append-only audit delivery
- [ ] Quarantined, scanned, encrypted document storage
- [ ] Consent and revocable property-level grants

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
