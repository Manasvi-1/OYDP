# Contributing to OYDP

OYDP is a private, owner-controlled development project. Contributions require repository-owner approval.

## Before a change

1. Read [`AGENTS.md`](AGENTS.md), [`README.md`](README.md), and [`docs/README.md`](docs/README.md).
2. Confirm the active surfaces: `apps/api` + `infra/db`. Do not treat root `oydp/` + `migrations/` as interchangeable.
3. Open a narrowly scoped issue or implementation proposal.
4. Identify the affected engine, trust boundary, data contract, and rollback plan.
5. Prefer evidence labels from the master engineering standard. Do not mark placeholders complete.

## Pull request checklist

- [ ] No secrets, customer deeds, proprietary datasets, or personal data committed
- [ ] API contracts and migrations documented under `infra/db` when schema changes
- [ ] Negative authorization and cross-tenant tests included where relevant
- [ ] Tests actually executed, with command and result recorded in the PR
- [ ] Privacy, source licensing, and geographic limitations considered
- [ ] No unverified claims of official integrations, legal status, or AI accuracy
- [ ] Reviewer approval obtained before merge

## Engineering discipline

- Keep PRs small and reviewable.
- Preserve untracked local work and existing behaviour; do not weaken security or authz to make a test pass.
- Record honest limitations. A green CI run is not production approval or an independent audit.
- Follow `.cursor/rules/oydp-master.mdc` for build, security, verification, and delivery expectations.

Avoid large unreviewable changes, premature microservices, and placeholder features described as complete.
