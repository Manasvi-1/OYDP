# OYDP verification register

Updated 25 October 2026. GitHub commit/tree and CI records are the implementation evidence; passing tests are not production certification.

| Scope | Evidence | Result |
| --- | --- | --- |
| PR #2 merged active API | Main `c489a4a`; runs 40198784340 and 40198784273 | 48 tests, no skips; dependency audit passed |
| PR #1 reconciliation | Head `e3d32af`; runs 40200582928, 40200582906, 40200582940 | 87 native PostGIS tests + 13 subtests, 48 active tests; no skips; audit/compile passed |
| PR #1 merged | Main `16fea27`; foundation/API/database workflows passed | Both backend histories preserved; separate schemas/contracts documented |
| First active private-access implementation | `71ffa34451067c3a282a328386dcb5bf092b16eb`; runs 40201131315, 40201131363, 40201131314 | 71 active tests; 87 reference tests + 13 subtests; no skips; dependency audit passed |
| Final reviewed implementation | `21d9bc0b9307caf41e5a01b4d3196831170a60fd`; runs 40201370379, 40201370432, 40201370460 | 72 active PostgreSQL/API tests; 87 reference tests + 13 subtests; no skips; audit/compile passed |

Local current-source checks: 31 active API/auth tests and 50 root API/policy tests + 13 subtests pass. Database acceptance is executed in native CI, not inferred from locally skipped cases. A TestClient dependency deprecation warning remains; it is not a failed test.

## Review and authorization

Owner explicitly requested finishing PR #1 and continuing the planned build. Implementation self-reviews are recorded in the PRs; no independent human/security approval is claimed. Copilot quota messages are non-approvals. Expected-head normal merges are used only after current-head checks pass; no server-enforced rules are bypassed.

## Still unverified or incomplete

Real identity-provider enrollment, MFA freshness and production configuration; Next.js UI; write delegation and claims in the active API; malware scanning/encrypted documents; independent immutable audit delivery; privacy/export/deletion/restore acceptance; data rights/legal review; external penetration test; all 13 engine journeys; production release approval. The root reference backend and active API do not have interchangeable data or startup contracts.

## Synchronization protocol

Code, tests, migrations, contracts and status updates travel together in feature PRs. Review CI for the latest head, not an earlier success. After merging, verify main's tree matches that head and check post-merge workflows. There is no unattended continuous chat-to-repository synchronization.

Latest-head checks, merge SHA and post-merge verification are recorded on [PR #3](https://github.com/Manasvi-1/OYDP/pull/3). Documentation-only follow-ups do not replace the requirement to check their own CI before merging.

## Current discovery/claims increment (API 0.4.0)

Code/tests/contracts are authored for keyset property/claim pages, creator/MFA claim append, immutable unverified attribution, audit rollback and deferred commit failure. Local active API/unit tests: 43 passed; native PostgreSQL cases require fresh CI. Final checks, reviewed head and merge evidence must be recorded on the feature PR. Existing 0.3.0 results above do not validate this change.

The first discovery/claims DB CI run executed 110 cases (108 passed, two test row-factory failures). Fixtures were corrected to dictionary rows without removing lock assertions. Added signed-token claim/discovery coverage and CI JUnit guards that reject skipped/empty acceptance reports. Current source is committed directly through GitHub after the local environment disconnected; do not claim a synchronized local checkout or local execution for these follow-ups. Fresh head CI is required.

## Verified native execution — 25 October 2026

Reviewed implementation: `68f2875c85e4d4fb371c554664a11b9de132cf1f`.
- Active API/PostgreSQL: **115 passed, zero skipped** — https://github.com/Manasvi-1/OYDP/actions/runs/40203433997
- Reference native PostGIS: **87 passed + 13 subtests, zero skipped** — https://github.com/Manasvi-1/OYDP/actions/runs/40203430633
- Unit/OpenAPI/compile/dependency audit: **passed**, no known dependency vulnerabilities reported — https://github.com/Manasvi-1/OYDP/actions/runs/40203434051

The database report guard confirmed no empty/skipped/failed acceptance cases. Deferred commit failure returns 503 and rolls back claim/audit; the signed-token journey and both pagination revocation locks passed. One TestClient dependency deprecation warning remains. This evidence supersedes pending database status above for that implementation. Documentation-only follow-up checks and merged-head results are recorded on PR #4: https://github.com/Manasvi-1/OYDP/pull/4.

The workspace disconnected after initial local checks. Follow-up source was committed directly in GitHub and tested by native CI; current local synchronization is not claimed. Independent human/security approval, real provider integration and production release remain pending.
