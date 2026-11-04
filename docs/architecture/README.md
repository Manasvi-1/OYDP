# Architecture decision record — ADR-001

**Status:** proposed and partially scaffolded.

## Decision
Use Next.js/TypeScript for user interfaces, a modular FastAPI monolith, PostgreSQL/PostGIS as the authoritative store, managed OIDC with MFA, and encrypted private evidence storage. Keep all 13 engines as bounded contexts sharing a single property identity and policy system.

## Why
A modular monolith avoids premature distributed transactions, inconsistent authorization checks and unnecessary operational cost. Internal module boundaries and explicit API contracts preserve the option to extract services if measured needs justify it.

## Trust boundaries
- Client input is untrusted. Identity is established by verified OIDC tokens, not caller-provided headers.
- Each property access requires object-level authorization and tenant isolation.
- RLS is defense in depth, not a substitute for verified membership.
- Untrusted uploads must be quarantined and scanned before permitted download.
- AI retrieval must be jurisdiction-scoped and treat documents as data, never instructions.
- Government data sources require verified rights; an accessible portal is not an API contract.
- Audit events must be committed atomically with business state and exported to an independent sink.

## Current limitations
The active API verifies RS256 access tokens and serves private property, grant, and unverified-claim routes. The web workspace can complete authorization-code sign-in against a configured issuer and calls that API from the server. A production identity provider has not been selected. Quarantine scanning exists; a certified malware product and an independent audit sink do not. The remaining engine journeys are still open. See [security gates](../implementation/SECURITY_GATES.md) and [web workspace](../implementation/WEB_UI.md).
