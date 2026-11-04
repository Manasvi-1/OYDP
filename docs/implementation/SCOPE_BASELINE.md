# Scope baseline

Recorded 4 November 2026 from `AGENTS.md`, `.cursor/rules/oydp-master.mdc`, `README.md`, `docs/ROADMAP.md`, and `docs/fundraising/FUNDER_PROPOSAL.md`. This file states the verified product boundary. It is not a release approval.

Evidence point: commit `95fce64798e7108cc4cf0b346f9f3e4a8df984ba` on open pull request [6](https://github.com/Manasvi-1/OYDP/pull/6) (`docs/oydp-master-execution-standard` → `main`) in `Manasvi-1/OYDP`. That commit message is "Add the first authenticated Next.js property workspace." The active OpenAPI document at that commit is version 0.4.0. Pull request 6 is open. It is not merged.

The local branch `feat/launch-1-drop-1` is at the same commit and has uncommitted work. That work is not part of this baseline.

## Verified baseline

The built slice is pre-alpha.

| Capability | What is in the evidence point | Limit |
| --- | --- | --- |
| Private properties | API 0.4.0. A caller sees a property as its creator or while a grant is current. | Another tenant member does not receive the record by membership alone. |
| Unverified claims | Paginated discovery and an attributed claim ledger. The server fixes the claim as a user claim with status `unverified`. | A client cannot mark a claim official. Statements are stored text. |
| Expiring read grants | The creator can grant and revoke a read. Expiry is enforced. The grant window is at most 30 days. | A read grant does not authorize writing a claim. |
| First web workspace | `apps/web` on pull request 6. It lists private properties, creates a record, opens one record, appends an unverified claim, and grants or revokes expiring read access. The access token stays in an httpOnly cookie. | It does not enroll, refresh, or revoke an identity provider. It does not upload documents, correct records, delegate writes, or run the other engines. `npm test` covers session and query construction. It is not a browser end-to-end run. |

The active service is `apps/api` on the public schema, with string identity subjects and configured token verification. The root `oydp/` tree and `migrations/` remain the separate reference backend from pull request 1. The two are not interchangeable, and their data is not synchronized.

Native CI for ancestor `68f2875c85e4d4fb371c554664a11b9de132cf1f` records 115 active API and PostgreSQL tests passed, with zero skipped, plus the reference PostGIS suite and the OpenAPI and dependency audit named in `docs/fundraising/FUNDER_PROPOSAL.md`. That run does not cover the workspace commit. This record does not repeat those tests. Passing tests are evidence about that run. They are not production security and not an independent audit.

Launch geography, when a later feature is allowed, is Bengaluru Urban, Bengaluru Rural, other Karnataka districts, and Hyderabad. A feature allowed for one place is not assumed for another.

## Thirteen engines

All 13 engines are bounded launch commitments. None is complete. "Partial" means only the private-property slice in the table above.

| ID | Engine | State |
| --- | --- | --- |
| E01 | Property Identity & Evidence Graph | Partial. Private records, unverified claims, and expiring read grants only. No evidence-document graph and no title certification. |
| E02 | AI Property Advisor | Not built |
| E03 | Transaction & Legal Workspace | Not built |
| E04 | Living Property Passport | Not built |
| E05 | Ownership Action Engine | Not built |
| E06 | OYDP Real Estate Academy | Not built |
| E07 | SpatialLedger GIS Intelligence | Not built |
| E08 | Property Valuation & Market Intelligence | Not built |
| E09 | AI Layout & Architecture Concept Studio | Not built |
| E10 | Development & Business Feasibility | Not built |
| E11 | Marketplace & Professional Network | Not built |
| E12 | Time-Versioned Spatial Digital Twin | Not built |
| E13 | Institutional API & Evidence Attestations | Not built |

`docs/ROADMAP.md` still leaves property update, write delegation, correction, browser end-to-end coverage, and live identity-provider enrollment open. General availability still requires 13 real engine journeys and the other unchecked gates in that roadmap.

## Recorded decisions

1. **Modular monolith.** One Next.js workspace, one FastAPI service, and one PostgreSQL database with PostGIS. Thirteen separately deployed services are not the launch shape.
2. **PostgreSQL / PostGIS.** Versioned migrations and row-level security are the data foundation. A graph database is not the launch store.
3. **No portal copying until a qualified rights review.** Naming Kaveri, e-Aasthi, e-Swathu, Bhoomi, Dharani / Bhu Bharati, TS RERA, TS-bPASS, BBMP, BDA, BMRDA, GHMC, or HMDA states the problem. An open website is not a license to query, store, or redistribute those records. Scraping stays unauthorized until a qualified review names each source and the permitted use.
4. **No title guarantee.** OYDP does not verify title, certify ownership, clear encumbrance, or eliminate fraud. A user claim stays unverified.
5. **No government affiliation.** OYDP is not a government service and is not integrated with the portals or authorities named above.
6. **No guaranteed valuation.** OYDP does not guarantee a value, an investment return, a feasibility result, or an architectural or planning approval.

Deterministic code decides authorization, money, policy, validation, and critical state changes. Model output may explain a source it can cite and must abstain when it cannot. It does not grant access, set a price, move money, or mark a claim verified.

Document 1, the uploaded master blueprint OYDP-MASTER-001, controls the written product scope. It is a research and design document. It is not built software. The repository controls what is built. In this repository, `docs/reference/06-25_OYDP_Master_Consolidated_Blueprint-1-.txt` is the controlled product-scope extract.

## Documents 2–7

Documents 2–7 are non-binding sketches. They are not an implementation, not the codebase, and not evidence of deployed infrastructure. They do not replace Document 1 or this repository.

Documents 2, 3, 4, and 7 are generated sketches. Documents 5 and 6 are the same code dump twice. They include mock intelligence, sample coordinates, and example secrets. Their regional arithmetic is not a forecast. Archive them only with a cover note that they are non-binding, and remove example passwords, tokens, and cloud credential snippets before anyone outside the repository sees them.

## Claims not recorded

- The uncommitted tree on `feat/launch-1-drop-1` is not the baseline. That includes local edits that add label and jurisdiction correction, owner-delegated write grants, a loopback identity realm, and migration `008`. The committed workspace note at `95fce64` says the workspace does not correct records or delegate writes.
- The working-tree engine register line that treats audited correction and owner-delegated write as present is not adopted here.
- No engine is marked complete. E01 is partial only for the slice named above.
- Pull request 6 is not described as merged.
- The 115-test run is not described as covering `apps/web`.
- Market figures in the funder packet are not adopted as revenue, a forecast, or a fact.
- This repository is not described as production-secure, independently audited, or ready for a public launch.
