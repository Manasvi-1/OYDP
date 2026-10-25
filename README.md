# OYDP — Own Your Dream Property

**Property intelligence. Evidence-led decisions. One continuous property lifecycle.**

OYDP is an India-first property decision and lifecycle platform under active development. It is designed to connect property identity, evidence provenance, collaborative due diligence, ownership workflows, geospatial context, transparent financial models and professional services within a single permissioned workspace.

> **Engineering status — pre-alpha.** This repository contains the controlled product design and an initial backend/database foundation. It is **not** a launched product, government-integrated verification service, or completed 13-engine application. This is a tested pre-alpha backend slice; the full application remains under development.

## Why OYDP exists

Property decisions are fragmented across documents, public portals, advisers, listings, spreadsheets and disconnected conversations. OYDP's proposed differentiator is a persistent, property-specific workspace where claims can be traced to their sources, collaborators receive revocable permissions, and every consequential result carries its evidence and limitations.

**No unverified ownership certification. No invented official data access. No guaranteed valuations.**

## Product scope

All 13 engines remain planned release commitments; none is marked production-complete.

| ID | Engine | Intended responsibility |
| --- | --- | --- |
| E01 | Property Identity & Evidence Graph | Canonical property candidates, identifiers, provenance and conflicts |
| E02 | AI Property Advisor | Jurisdiction-scoped, source-grounded procedural guidance |
| E03 | Transaction & Legal Workspace | Invited diligence, requests, offers and review history |
| E04 | Living Property Passport | Private records, events, selective sharing and exports |
| E05 | Ownership Action Engine | Tracked tasks, evidence and consent-based reminders |
| E06 | OYDP Real Estate Academy | Reviewed learning tracks and assessments |
| E07 | SpatialLedger GIS Intelligence | Source-attributed mapping and spatial overlays |
| E08 | Valuation & Market Intelligence | Licensed comparables and explainable price ranges |
| E09 | AI Layout & Architecture Concept Studio | Concept-only plot and massing alternatives |
| E10 | Development & Business Feasibility | Reproducible scenario and cash-flow calculations |
| E11 | Marketplace & Professional Network | Consent-based listings and moderated enquiries |
| E12 | Time-Versioned Spatial Digital Twin | Versioned spatial representations and history |
| E13 | Institutional API & Evidence Attestations | Grant-scoped, audited, read-only integrations |

## Architecture

The target is a **modular monolith**, not 13 independently deployed services.

```text
Browser / role-specific Next.js interfaces  [planned]
                    |
         OIDC identity + policy layer        [planned]
                    |
         FastAPI modular backend             [property API implemented]
                    |
       PostgreSQL / PostGIS + RLS            [migrations + native tests]
                    |
     Evidence storage / workers / audit      [planned]
```

Core engineering principles: verified identity before access, server-side object authorization, tenant isolation at both application and database layers, explicit source lineage, bounded background jobs, privacy by design and deterministic calculations where correctness is essential.

See [architecture](docs/architecture/README.md) and [security model](docs/security/README.md).

## Implementation status

| Area | State | Evidence |
| --- | --- | --- |
| Product requirements and architecture | Documented | Controlled source blueprints |
| API foundation | Authenticated property and read-access API | `apps/api/app/main.py` |
| Property database schema | Versioned, checksum-verified migrations | `infra/db/`; PostgreSQL CI |
| Tenant isolation | Forced RLS, membership checks, evidence tenant integrity | 67 PostgreSQL/API cases passed at `68f2875` |
| Authentication | RS256 access-token verifier and DB membership checks implemented | RSA negative tests; provider configuration still required |
| API/authentication/pagination/CI guard tests | 48 passed in GitHub CI | `apps/api/tests/`; 115 total with DB integration |
| Next.js application | Not implemented | Pending |
| All 13 end-to-end engine journeys | Not implemented | GA gate |
| Production deployment | Not performed | Not production-ready |

**Do not interpret committed files, passing smoke tests, or documentation as evidence of production security.**

## Repository layout

```text
OYDP/
├── .github/workflows/       # CI definitions
├── apps/
│   ├── api/                 # FastAPI backend
│   └── web/                 # Reserved for Next.js UI
├── infra/db/                # Versioned SQL migrations
├── docs/
│   ├── architecture/        # Architecture decisions and boundaries
│   ├── security/            # Threats, authorization and release gates
│   ├── implementation/      # Phase progress and engineering tickets
│   └── reference/           # Controlled specifications when available
├── AGENTS.md                # AI-assisted engineering guardrails
├── compose.yaml             # Local PostGIS development service
└── README.md
```

Directories described as planned may not yet exist on the default branch.

## Local development — foundation only

Prerequisites: Python 3.12+, Docker with Compose, and Git. Create a private local `.env` from `.env.example` and replace the example password.

```bash
git clone https://github.com/Manasvi-1/OYDP.git
cd OYDP
git switch main
cp .env.example .env
docker compose up -d db
python -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r apps/api/requirements.lock
PYTHONPATH=apps/api python -m pytest -q apps/api/tests
PYTHONPATH=apps/api uvicorn app.main:app --reload
```

On Windows PowerShell, use `Copy-Item .env.example .env`, `.venv\Scripts\Activate.ps1`, and `$env:PYTHONPATH="apps/api"` instead of the corresponding POSIX commands.

The current Compose service starts the database only. Run the [migration and runtime-role provisioning commands](docs/implementation/DATABASE_FOUNDATION.md) separately. Property routes require configured OIDC, an access token, and a pre-provisioned tenant membership. See [API setup](docs/implementation/PROPERTY_API.md). These instructions are **not** a complete working application setup.

## Engineering workflow

1. Read [AGENTS.md](AGENTS.md) and the controlled master specification.
2. Start a narrowly scoped feature branch and write an implementation plan.
3. Add schema changes, contracts, negative authorization tests and migration verification.
4. Run tests against real isolated infrastructure; document commands and outcomes.
5. Submit a reviewed PR with risk notes and rollback instructions.
6. Merge only after security and functional acceptance gates pass.

## Release boundaries

The initial geographic program covers Bengaluru Urban, Bengaluru Rural, other Karnataka districts and Hyderabad, subject to **jurisdiction-specific source rights and professional review**. Government portals are independent authorities; availability of a website does not grant API or redistribution rights.

General availability requires 13 genuine engine journeys plus legal/data-rights review, security assessment, privacy and consent validation, grounded AI and calculator evaluation, recovery drills, pilot economics and signed release approval.

## Roadmap

**Now:** API 0.4.0 private discovery and unverified claims passed native CI; complete the first authenticated UI and real provider setup.  
**Next:** Evidence lineage, private documents, audit outbox, transaction collaboration and first complete UI journey.  
**Later:** GIS, valuation, concept modeling, feasibility, marketplace, temporal twin and institutional API, with validated data rights and cross-engine testing.

See [implementation status](docs/implementation/PHASE_04_STATUS.md) and [engineering roadmap](docs/ROADMAP.md).

## Security and responsible disclosure

Do not open public issues containing vulnerabilities, credentials, property documents or personal information. See [SECURITY.md](SECURITY.md). Never commit live customer data, recovery keys or third-party proprietary datasets.

## Ownership and licensing

Copyright and licensing decisions have not yet been finalized. **No open-source license is granted by this repository as currently documented.** Third-party dependencies retain their respective licenses. Contact the repository owner for usage or contribution authorization.

---

**OYDP is being engineered for verifiable property workflows, not unsupported claims of certainty.**


## Latest verified backend build

Implementation `68f2875`: [115 active API/PostgreSQL tests passed](https://github.com/Manasvi-1/OYDP/actions/runs/40203433997), zero skips. [87 reference-backend tests plus 13 subtests passed](https://github.com/Manasvi-1/OYDP/actions/runs/40203430633), zero skips. [API, OpenAPI and dependency audit passed](https://github.com/Manasvi-1/OYDP/actions/runs/40203434051). This is pre-alpha backend evidence, not production or independent security approval. See [verification register](docs/implementation/VERIFICATION_REGISTER.md).

## Reconciled earlier foundation (PR #1)

The earlier property-grants prototype is retained in `oydp/`, `migrations/`, and `tests/test_*.py`, with its own native PostGIS CI. It is a separately tested compatibility/reference backend, not mounted by `app.main:app`. Its UUID-subject/pinned-key API and `oydp` schema differ from the canonical `apps/api` string-subject/JWKS API and public schema. Do not run both as interchangeable APIs or assume data is synchronized. See [reconciliation and next implementation](docs/implementation/PR1_RECONCILIATION.md).

## Active API privacy update

API 0.3.0 adds creator-private records, expiring read grants, MFA-gated creation/sharing/revocation and audited access changes. See [canonical access contracts and upgrade](docs/implementation/CANONICAL_PROPERTY_ACCESS.md). This supersedes earlier tenant-shared behavior. CI on the current feature head is the acceptance evidence.

## Active API 0.4.0 increment

Paginated private property discovery and attributed unverified claim recording/history passed native CI. Claims require creator/write-role/MFA authority; read grants permit history reads only. The [active OpenAPI contract](apps/api/openapi.json) and [discovery/claims guide](docs/implementation/DISCOVERY_CLAIMS.md) describe limits, upgrade steps, cursor semantics and remaining release gates. Current-head CI, rather than earlier test counts, determines acceptance.
