# Sprint status

**Sprint focus:** E01 property dedup **candidates** (API 0.20.0 + `/dedup` web). Disposition PR #43/#44 on main. Do not merge unless CI green and gates re-confirmed.  
**Date:** 2026-11-26.

## Goals

| Goal | State |
| --- | --- |
| Wire Next.js CSP middleware (AUD / presentation) | Done (PR #38) |
| Close OpenAPI AUD-001 drift | Done (`export_active_openapi.py --check`) |
| Migration 020 audit/source/assertion gates | Implemented; portable PG **250 passed** |
| T-NEXT-011 web graph/conflicts | **VERIFIED** on main (PR #37) |
| T-NEXT-012 web attribution write/display | Done on PR #38 branch (API already had PUT) |
| Withdrawn-source conflicts for docs/reviews | Done (API 0.17.0) |
| Process-local rate limit + docs exposure posture | Done (honest non-distributed) |
| PostGIS IDOR / local PostGIS | **BLOCKED** (`T-NEXT-009`, no Docker) |
| Membership-revoke session posture | Done on main (PR #41). Live IdP revocation still blocked |
| Evidence conflict dispositions | VERIFIED on main (PR #43/#44) |
| Property dedup candidates (no auto-merge) | TESTED on `feat/property-dedup-candidates` (API 0.20.0; mig 023; 161 unit + 118 PG; web 54) |
| Live Keycloak verification | Blocked |
| GA readiness | Not in sprint — gates open |

## In flight

- Property dedup candidates feature branch pending PR CI / merge gates.

## Carry-over

- Automatic property merge (explicitly out of scope until designed); local PostGIS acceptance; scanner adapter; live IdP; engines E02/E04–E13; independent review; distributed rate limiting.
