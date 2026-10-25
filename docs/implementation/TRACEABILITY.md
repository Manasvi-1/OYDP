# Specification-to-implementation traceability

Source hierarchy: controlled OYDP master blueprint (2026-10-16), 13-engine product specification, architecture and development roadmap. Never reinterpret a design specification as implementation evidence.

| Requirement | Code location | Verification | State |
| --- | --- | --- | --- |
| E01 property identity | apps/api/app/main.py, infra/db/001_property_identity.sql | Create/read + append-only audit; real API/DB tests authored | PARTIAL |
| E01 provenance | infra/db/003_provenance.sql | Tenant lineage PostgreSQL acceptance tests | PARTIAL |
| Tenant authorization | infra/db/001_property_identity.sql, 002_membership.sql | PostgreSQL RLS tests and API denial tests | PARTIAL |
| Identity verification | apps/api/app/auth.py | RSA token rejection and JWKS selection tests | PARTIAL |
| E02 AI advisor | Not implemented | None | PENDING |
| E03 transaction workspace | Not implemented | None | PENDING |
| E04 property passport | Not implemented | None | PENDING |
| E05 ownership actions | Not implemented | None | PENDING |
| E06 academy | Not implemented | None | PENDING |
| E07 GIS | Not implemented | None | PENDING |
| E08 valuation | Not implemented | None | PENDING |
| E09 concept studio | Not implemented | None | PENDING |
| E10 feasibility | Not implemented | None | PENDING |
| E11 marketplace | Not implemented | None | PENDING |
| E12 spatial twin | Not implemented | None | PENDING |
| E13 institutional API | Not implemented | None | PENDING |

## Synchronization protocol
1. GitHub branch + commit SHA is the implementation record; chat statements are not proof.
2. Every feature change updates this matrix and the verification register in the same PR.
3. PR description must report commands executed, outcomes and pending controls.
4. CI validates committed code; independent reviewers approve security/legal claims.
5. After merge, update the README status and roadmap against main's merged commit.
6. Future conversations should re-fetch GitHub state before reporting progress.
7. There is no continuous two-way sync between ChatGPT conversations and GitHub without an explicitly configured integration or scheduled workflow.


## Database foundation update — 25 October 2026

See [database implementation and acceptance](DATABASE_FOUNDATION.md) for migration tooling, runtime-role provisioning, composite tenant integrity, 13 PostgreSQL tests and the dedicated CI job. Local API tests: 3 passed; database tests: 13 skipped pending PostgreSQL execution. Earlier unverified items remain open unless this record explicitly supersedes them. OIDC and property CRUD remain disabled.

## Current slice — supersedes historical status above
RS256 access-token validation, per-request membership, tenant-shared property create/read, transactional append-only audit, and 24 additional/expanded API and DB cases are authored. See PROPERTY_API.md and the current CI result; real provider interoperability, property grants, UI and all other engines remain incomplete.

## Verified authenticated API execution — 25 October 2026

Implementation commit: `1cc439843c354d119222e243a5dd051df5b11d8c`.
[Database security CI](https://github.com/Manasvi-1/OYDP/actions/runs/40198550858): **48 passed, zero skipped**, one TestClient dependency deprecation warning. This includes 24 API/auth tests and 24 PostgreSQL/API integration cases.
[API and dependency audit CI](https://github.com/Manasvi-1/OYDP/actions/runs/40198550853): passed; hash-locked dependency installation and pip-audit succeeded with no known vulnerabilities reported.
All 36 tracked source files matched GitHub blob hashes before this evidence-only update. These results supersede pending CI status above for the tested implementation. This follow-up changes documentation only; its own checks must also pass before merge. Independent security/human review, live provider onboarding and production approval remain unfulfilled. One passing suite does not validate the whole platform.
