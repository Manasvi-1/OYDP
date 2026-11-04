<div align="center">

<!-- brand accent — deep teal / slate, not purple -->
<img
  src="https://img.shields.io/badge/OYDP-Own%20Your%20Dream%20Property-0F766E?style=for-the-badge&labelColor=0F172A"
  alt="OYDP — Own Your Dream Property"
/>

# OYDP

### Own Your Dream Property

**India-first continuous property lifecycle** — a permissioned workspace where people, evidence, and spatial context stay together across the life of a property.

[![Status](https://img.shields.io/badge/status-pre--alpha-F59E0B?style=flat-square&labelColor=0F172A)](#where-we-actually-are)
[![Engines](https://img.shields.io/badge/engines-13%20planned-0F766E?style=flat-square&labelColor=0F172A)](#the-13-engines)
[![Shape](https://img.shields.io/badge/shape-modular%20monolith-334155?style=flat-square&labelColor=0F172A)](#how-it-fits-together)
[![API](https://img.shields.io/badge/API-0.3%20privacy%20·%20.4%20discovery-0EA5E9?style=flat-square&labelColor=0F172A)](#api-increments)
[![Tests](https://img.shields.io/badge/backend%20build-68f2875%20·%20115%20tests-64748B?style=flat-square&labelColor=0F172A)](#latest-verified-backend-build)

<br/>

<sub>
Honest pre-alpha. Not a registry. Not a government portal. Not production-ready.
</sub>

</div>

---

## Why OYDP exists

Indian property work is fragmented. Title papers live in one drawer, survey sketches in another, WhatsApp threads elsewhere, and every “official” claim needs careful verification. People lose the thread between discovery, claim, diligence, and long-term ownership.

OYDP’s bet is simple: give serious participants a **permissioned workspace** where lifecycle state and **evidence** can travel together — without pretending we are the government, and without inventing data we do not have.

We are building that foundation carefully. Pre-alpha means the skeleton is real; the product is not finished.

---

## What we do **not** claim

Please read this before anything else.

| We do **not** | Meaning |
| --- | --- |
| Issue unverified ownership certificates | OYDP is not proof of title |
| Invent or scrape “official” data | No fabricated registry / survey / mutation records |
| Guarantee valuations | Any value models are advisory research, never a promise |
| Speak for government systems | No claimed API access to state or central land portals |
| Ship production / gov-verified software | This repo is pre-alpha engineering |

If a feature would require us to fake certainty, we leave it unbuilt.

---

## The 13 engines

Thirteen engines are **planned release commitments**. None are production-complete. Names below match the controlling blueprint and [`docs/ENGINE_REGISTER.md`](docs/ENGINE_REGISTER.md). Status language there is authoritative; this table is orientation only.

| ID | Engine | Notes |
| :---: | --- | --- |
| **E01** | Property Identity & Evidence Graph | Partial pre-alpha slice on `apps/api` |
| **E02** | AI Property Advisor | Planned |
| **E03** | Transaction & Legal Workspace | Bounded diligence requests only; rest planned |
| **E04** | Living Property Passport | Planned |
| **E05** | Ownership Action Engine | Planned |
| **E06** | OYDP Real Estate Academy | Planned |
| **E07** | SpatialLedger GIS Intelligence | Planned |
| **E08** | Property Valuation & Market Intelligence | Planned |
| **E09** | AI Layout & Architecture Concept Studio | Planned |
| **E10** | Development & Business Feasibility | Planned |
| **E11** | Marketplace & Professional Network | Planned |
| **E12** | Time-Versioned Spatial Digital Twin | Planned |
| **E13** | Institutional API & Evidence Attestations | Planned |

<div align="center">
<img src="https://img.shields.io/badge/E01–E13-planned%20only-0F766E?style=flat-square&labelColor=0F172A" alt="All engines planned only" />
<img src="https://img.shields.io/badge/production--complete-0%20of%2013-DC2626?style=flat-square&labelColor=0F172A" alt="Zero engines production-complete" />
</div>

---

## How it fits together

Modular monolith: one deployable backend today, clear module boundaries so engines can grow without a microservice zoo.

```mermaid
flowchart LR
  B["Browser / web app"] --> O["OIDC sign-in"]
  O --> F["FastAPI modular monolith"]
  F --> P[("Postgres + PostGIS<br/>Row Level Security")]
  F -. planned .-> E["Evidence store"]
  F -. planned .-> W["Background workers"]

  style B fill:#0F172A,stroke:#0F766E,color:#E2E8F0
  style O fill:#134E4A,stroke:#0F766E,color:#E2E8F0
  style F fill:#0F766E,stroke:#99F6E4,color:#F8FAFC
  style P fill:#1E293B,stroke:#64748B,color:#E2E8F0
  style E fill:#334155,stroke:#94A3B8,color:#CBD5E1,stroke-dasharray: 4 3
  style W fill:#334155,stroke:#94A3B8,color:#CBD5E1,stroke-dasharray: 4 3
```

ASCII sketch if Mermaid is collapsed:

```
Browser ──► OIDC ──► FastAPI (modular monolith)
                         │
                         ▼
              Postgres / PostGIS + RLS
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
     evidence store              workers
        (planned)               (planned)
```

---

## Where we actually are

Honest status — green means “exists and is useful in-repo,” amber means “partial / scaffolding,” slate means “planned.”

| Surface | Status | Notes |
| --- | :---: | --- |
| FastAPI backend foundation | ![amber](https://img.shields.io/badge/-partial-F59E0B?style=flat-square) | Pre-alpha; see build note below |
| Postgres + PostGIS + RLS | ![amber](https://img.shields.io/badge/-partial-F59E0B?style=flat-square) | Spatial + tenancy primitives in progress |
| Web client | ![amber](https://img.shields.io/badge/-scaffolding-F59E0B?style=flat-square) | Not a finished product UI |
| OIDC auth path | ![amber](https://img.shields.io/badge/-wired-F59E0B?style=flat-square) | Foundation for permissioned access |
| Evidence store / workers | ![slate](https://img.shields.io/badge/-planned-64748B?style=flat-square) | On the architecture diagram for a reason |
| Engines E01–E13 | ![slate](https://img.shields.io/badge/-planned-64748B?style=flat-square) | Release commitments, not shipped modules |
| Government data feeds | ![red](https://img.shields.io/badge/-not%20claimed-DC2626?style=flat-square) | We do not invent or assert access |

### Dual-backend reconciliation

> **Authority.** Evolve only `apps/api` + `infra/db` (public schema, role `oydp_app`). Root `oydp/` + `migrations/` is a **frozen PR #1 reference** (schema `oydp`, role `oydp_runtime`): separately CI-tested, not mounted, not interchangeable. See [`docs/implementation/PR1_RECONCILIATION.md`](docs/implementation/PR1_RECONCILIATION.md) and `AGENTS.md`.

### API increments

- **API 0.3 — privacy** — privacy-respecting defaults for workspace data; foundation for grants.
- **API 0.4 — discovery / claims** — early discovery and claims surfaces on top of that privacy base.

These are incremental pre-alpha slices, not versioned public product APIs with SLAs.

### Merged workspace migrations `008`–`014`

Workspace migrations **008 through 014** are merged into the shared migration line. Apply them in order on a fresh foundation database. Do not cherry-pick mid-stream; if you fork schema locally, rebase onto the merged sequence before opening a PR.

---

## Repo layout

```
OYDP/
├── apps/
│   ├── api/          # Canonical FastAPI surface (active)
│   └── web/          # Authenticated Next.js workspace (pre-alpha)
├── infra/db/         # Canonical checksum migrations (public schema)
├── oydp/             # Frozen PR #1 reference package (not mounted)
├── migrations/       # Reference oydp-schema migrations only
├── docs/             # Design, boundaries, engineering notes
├── AGENTS.md         # Agent & contributor gates — read before automated edits
├── SECURITY.md       # Vulnerability disclosure
└── README.md         # You are here
```

Exact folder names may evolve as the dual-backend reconciliation lands; when docs and tree disagree, trust `AGENTS.md` and the latest engineering note.

---

## Local foundation setup

### POSIX (Linux / macOS)

1. Clone the repo and enter it.
2. Install Python 3.11+, Node (for web), Docker (Postgres/PostGIS recommended).
3. Copy `.env.example` → `.env` and fill OIDC + database URLs for **local** use only.
4. Bring up PostGIS, run migrations through **014**, start the API from the **canonical** backend path (see reconciliation warning).
5. Run the test suite before you trust your checkout.

```bash
# illustrative — follow docs/ and AGENTS.md for the canonical commands
cp .env.example .env
docker compose up -d db          # PostGIS
# run migrations  →  start API  →  optional web
```

### Windows notes

- Prefer **WSL2** for parity with POSIX scripts and Docker Desktop’s Linux engine.
- Native PowerShell works for editing; treat shell scripts as WSL-first unless a `*.ps1` helper exists.
- Path length and CRLF: keep `core.autocrlf` sane and avoid binding PostGIS data dirs to non-WSL paths when possible.

We do not document a production deploy here — because we are not production.

---

## Engineering workflow & release boundaries

- Read **[`AGENTS.md`](AGENTS.md)** before agent-driven or bulk edits — security and contribution gates stay intact.
- Keep PRs small; say which engine or API increment you are touching.
- **Release geography (near-term):** Bengaluru → Karnataka → Hyderabad. Do not assume pan-India coverage, data, or compliance.
- No silent “official data” integrations. If a PR needs an external registry feed, it needs an explicit design note and honest sourcing.

---

## Roadmap

| Horizon | Focus |
| --- | --- |
| **Now** | Keep `apps/api` + `infra/db` as sole evolving authority; harden OIDC/dev gates, RLS, and Property Workspace evidence/document paths |
| **Next** | Real malware scanner adapter; production identity enrollment; MFA freshness; independent audit sink; deepen remaining engines without claiming completion |
| **Later** | Broader engine delivery (E02–E13 beyond current slices); workers; carefully scoped regional expansion past Bengaluru / Karnataka / Hyderabad — still without fake gov certainty |

---

## Security

Found a vulnerability? Please use **[`SECURITY.md`](SECURITY.md)** — do not open a public issue with exploit detail.

We are pre-alpha. That is not an excuse for sloppy auth, leaked secrets, or disabled RLS in shared environments. It *is* a reason to avoid marketing language like “SOC 2 certified” until those programs actually exist.

---

## Ownership & licensing

Ownership and licensing are **not finalized**. Do not assume OSI open source, commercial rights, or contribution terms beyond what is written in-repo today. If you need clarity for a partnership or fork, ask the founder before shipping derivatives.

---

## Latest verified backend build

<div align="center">

<img src="https://img.shields.io/badge/commit-68f2875-0F766E?style=for-the-badge&labelColor=0F172A&logo=github" alt="commit 68f2875" />
<img src="https://img.shields.io/badge/tests-115%20passing-334155?style=for-the-badge&labelColor=0F172A" alt="115 tests passing" />

</div>

This is **pre-alpha evidence only** — a checkpoint that the backend foundation held under its then-current suite. It is not a release, not a compliance attestation, and not a claim that engines or the web app are done.

---

## Docs & gates worth keeping open

| Doc | Why |
| --- | --- |
| [`SECURITY.md`](SECURITY.md) | Disclosure path |
| [`AGENTS.md`](AGENTS.md) | Automation / contributor gates |
| `docs/` | Boundaries, design, regional notes |

---

<div align="center">

**OYDP** — Own Your Dream Property

<sub>Built carefully in Bengaluru. India-first. Evidence over theatre.</sub>

</div>
