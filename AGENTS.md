# Codex agent instructions — OYDP

You are developing OYDP (Own Your Dream Property). Treat `docs/reference/06-25_OYDP_Master_Consolidated_Blueprint-1-.txt` (controlled PDF text extract; see `docs/reference/manifest.json`) as the controlling product-scope reference and the 13-engine specification and development roadmap as supporting artifacts. Legacy PropertyTrust documents are historical context, not the current public product name.

## Non-negotiable scope
- Preserve all 13 engines as genuine bounded launch commitments; do not silently delete, merge away, or label placeholders complete.
- Respect coverage-specific regulatory/data limitations for Bengaluru Urban, Bengaluru Rural, other Karnataka districts, and Hyderabad.
- Never assert title verification, governmental affiliation, official integration, guaranteed valuation, or approved architectural designs without attributable verification.
- Prefer a modular monolith to 13 microservices.

## Engineering conduct
1. Inventory what exists before modifying code. Differentiate plans from implemented, tested behavior.
2. Start with project scaffolding, repeatable local dev environment, security threat model, database schema, and tenant-aware access checks.
3. Write executable tests, including negative authorization and cross-tenant tests, before marking a task done.
4. Add OpenAPI contracts, migrations, and documentation for each functional module.
5. Treat uploaded documents as untrusted data; enforce scanned, encrypted and authorized access.
6. Use deterministic code for finance and permissions. AI outputs must be source-grounded with abstention on unknowns.
7. Use environment variables for secrets; never commit tokens or private property records.
8. Keep commits small, work on feature branches, create PRs for review; do not deploy publicly or incur paid services without explicit approval.
9. Report changed files, tests actually run, failures, blockers, and what remains. No invented test outcomes.

## Delivery standard
The binding execution standard is `.cursor/rules/oydp-master.mdc`. For approved work: build real behavior, apply the security controls, execute the relevant tests, review the diff, then commit and push a feature branch. A test counts as passed only when that test executed and passed. Merge to `main`, deploy, and publish still require separate approval. Preserve untracked local work, `apps/web`, and PR #5.

## Baseline already on main
The Property Identity API, tenant isolation, and unverified claim ledger already exist on `main`. Do not rebuild that slice from the historical first task below. Re-inspect Git before relying on any status note.

## First task
Read the provided PDF requirements, propose implementation tickets, and create a working initial monorepo skeleton with Next.js web, FastAPI API, PostgreSQL/PostGIS local Docker services, CI smoke tests, and a security-oriented README. First add a phased plan, then implement the smallest testable vertical slice for Property Identity + tenant isolation. Do not substitute synthetic mock endpoints for production acceptance.

## Current repository boundaries
- Inventory the current main tree and every open PR before starting a new increment; reconcile existing work before duplicating it.
- Active service: apps/api + infra/db, public schema, role oydp_app, string OIDC subjects and configured JWKS. Root oydp/ + migrations/ is a frozen, separately tested reference backend from PR #1 (schema oydp, role oydp_runtime); no automatic data synchronization or interchangeable startup. scripts/migrate.py rejects the root migrations/ path.
- Active tests: PYTHONPATH=apps/api:. python -m pytest apps/api/tests tests/integration. Reference tests: PYTHONPATH=. python -m pytest tests/test_api.py tests/test_database.py tests/test_foundation.py. Keep discovery separate to avoid duplicate module names. Green reference CI is not active-API acceptance.
- Preserve applied SQL migration checksums; add new migrations under infra/db only. Treat independent human/security review as pending unless actual reviewer evidence exists.
