# Foundation implementation plan — 23 October 2026

Controlling scope: OYDP-MASTER-001. All 13 engines remain GA commitments.

1. Preserve and run the attached policy/provenance tests.
2. Implement versioned PostgreSQL schema: memberships, property candidates, explicit grants, assertions and transactional audit outbox. Enforce tenant consistency with composite foreign keys, forced row security and a non-owner runtime role.
3. Implement a FastAPI slice for creating, listing and reading property candidates and recording user claims. Verify RS256 JWT signature, issuer, audience, expiry and subject before selecting tenant. Check current database membership and grants on each operation.
4. Verify SQL isolation, rollback and migrations; test API contracts and token rejection. Separate embedded PostgreSQL checks from native PostgreSQL integration acceptance.
5. Continue to OIDC provider integration, PostGIS, evidence scanning, revocation delivery, the Next.js interface and browser E2E. These are required, not completed by the backend slice.

Design target: professional diligence workspace for a private property candidate. Main outcome: create a candidate, distinguish claims from reviewed evidence, and control reviewer access. Start with the evidence record, not a grid advertising 13 engines. Unknown jurisdiction remains visibly unresolved. Shared ChatGPT reference was inaccessible (redirected to logged-out home), so reference-dependent visual design is pending.

No public deployment, paid service, official data integration or legal certification is authorized by this development milestone.
