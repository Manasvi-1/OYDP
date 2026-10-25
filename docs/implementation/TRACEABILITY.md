# Specification-to-implementation traceability

Source hierarchy: controlled OYDP master blueprint, 13-engine specification, architecture and roadmap. Design commitments do not establish runtime completion.

| Requirement | Active implementation | Evidence / state |
| --- | --- | --- |
| E01 property identity | apps/api/app/main.py; infra/db/001,004,006 | Private create/read/share implemented; discovery/claim ledger in API 0.4.0 under verification; full engine partial |
| Identity verification | apps/api/app/auth.py | RSA negative tests, JWKS selection, issuer/audience/expiry/type and AMR validation; real provider onboarding pending |
| Tenant membership and RLS | infra/db/002,004,006; scripts/migrate.py | Native PostgreSQL/API denial tests; restricted runtime role |
| Private property reads | infra/db/006; active API access endpoints | Creator/read-grant checks, same-tenant denial, expiry/revoke and concurrency tests |
| Access audit | infra/db/005,006 | Atomic append-only runtime audit, idempotence/rollback tests; external immutable delivery pending |
| Evidence provenance | infra/db/003,004,006 | Unverified attributed claim ledger + atomic claim audit under verification; document upload/professional/official verification pending |
| Earlier grant/claim model | Root oydp package; migrations/001,002 | Separately tested compatibility/reference backend from merged PR #1; no schema synchronization |
| E02 AI advisor | Not implemented | Pending |
| E03 transaction workspace | Not implemented | Pending |
| E04 property passport | Not implemented | Pending |
| E05 ownership actions | Not implemented | Pending |
| E06 academy | Not implemented | Pending |
| E07 GIS | Not implemented | Pending |
| E08 valuation | Not implemented | Pending |
| E09 concept studio | Not implemented | Pending |
| E10 feasibility | Not implemented | Pending |
| E11 marketplace | Not implemented | Pending |
| E12 spatial twin | Not implemented | Pending |
| E13 institutional API | Not implemented | Pending |

See CANONICAL_PROPERTY_ACCESS.md for active contracts, upgrade limits and current access behavior; VERIFICATION_REGISTER.md and the latest PR checks for actual executed results. No placeholders count as completed engines. Main commits are authoritative; records in chat alone are not proof.
