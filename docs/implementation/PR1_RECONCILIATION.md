# PR #1 reconciliation and next build

Review date: 25 October 2026. PR #1 head before reconciliation: `6f51378e63da22506dc671ee703b811fe3012736`. Main baseline: `c489a4a2fe29e6c50b308db6feadad153c06da5f` (PR #2).

## Verified inventory

PR #1 was open, draft, and conflicted with main. Its two final foundation workflow runs succeeded (39903885700 and 39903881726). Its implementation adds persistent candidates/claims, UUID-subject pinned-key authentication, MFA-gated API writes, scoped grants, creator-managed expiring sharing/revocation, audit outbox, native concurrency tests and extracted reference specifications. Copilot comments only report quota exhaustion; they are not approval.

PR #2 separately implemented a string-subject JWKS API, public schema, checksum migrations, restricted runtime role and 48 passing tests. It did not supersede all of PR #1's stronger authorization features.

## Conflict decisions

Retain the current main README, AGENTS, Compose, gitignore and Codex connection instructions. Preserve PR #1's other sources, migrations, policy/provenance tests and controlled reference extracts. Use the canonical hash-locked dependency environment for both suites, avoiding conflicting dependency pins. Scope each CI job's test discovery explicitly to avoid duplicate test-module names. Preserve both histories with a merge commit on PR #1's branch; do not force-push or discard either branch's work.

## Operational boundary

`apps/api/app/main.py` remains the canonical evolving API. The root `oydp` package is a separately tested compatibility/reference implementation, not mounted by that API. The packages have different schemas, runtime roles, subject types and contracts; there is no automatic data synchronization or compatible interchangeable startup. Root-package documents and OpenAPI describe that package only. Do not bootstrap root migrations against the canonical public schema or treat reference assertions as official verification.

This is a transitional source consolidation, not a claim that both implementations form one finished service. Root migrations have destructive down scripts intended only for disposable test fixtures. Neither package's audit storage is independently immutable.

## Next bounded build

Port property-specific creator/grant authorization and MFA-gated access changes into the canonical JWKS API, with additive checksum migrations, nonmember/same-tenant denial, grant expiry/revocation, atomic audit and real PostgreSQL acceptance tests. Existing public records without attributable creators must fail closed until explicitly repaired by a trusted administrator. Do not silently grant every tenant member access. Build the UI against the consolidated canonical contract afterward.

## Acceptance

Run PR #1's full native PostGIS suite (including concurrency tests), PR #2's 48-test suite, dependency audit and compilation on this reconciled head. Record results in the PR before merging. No independent human/security audit, live provider setup or production approval is implied.
