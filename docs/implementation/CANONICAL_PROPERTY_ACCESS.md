# Canonical private properties and access — active API

This document describes the private-property access model on the active JWKS API (`apps/api` + `infra/db`). It does not mount or synchronize the separate root-package schema. Read sharing, write delegation, corrections, and attributed claims are implemented on this path.

## Behavior and API contract

New property records are private to their creator within a verified tenant. Being another tenant member, or even having tenant owner/editor role, does not reveal another creator's record. Explicit non-expired read grants authorize recipients. Live write grants also authorize property SELECT (migration `011`) so delegated editors can reach write helpers without a separate read grant. Membership is checked and locked on every request; grant readers hold a shared grant lock through their transaction. Revocation waits for already-authorized transactions and prevents later reads; already-returned data cannot be retracted.

- POST `/v1/properties`: requires owner/editor membership and a signed access token with `amr` containing `mfa` or `otp`. `created_by` comes from the verified subject through the transaction context, never client input.
- GET `/v1/properties` / GET `/v1/properties/{id}`: creator, valid read grant, or live write grant, plus current membership. Forbidden and nonexistent properties both return 404. Output includes attributable `created_by`.
- PUT/DELETE `/v1/properties/{id}/access`: creator + owner/editor role + MFA; JSON `recipient_subject` and timezone-aware `expires_at` (share). Grants expire within 30 days. Exact repeat is idempotent. Collaborators cannot reshare.
- PUT/DELETE `/v1/properties/{id}/writers`: creator-managed write delegation to same-tenant owner/editor members; MFA required; expiry within 30 days.
- PATCH `/v1/properties/{id}`: creator or live write grantee; audited correction history.
- POST/GET `/v1/properties/{id}/claims`: attributed unverified claims; write requires creator or live write grant plus MFA.

Self-sharing, missing recipients, wrong-tenant recipients, invalid expiry and non-MFA sensitive actions are denied. This implements issuer-asserted MFA, not a fresh interactive MFA challenge; provider AMR semantics, auth_time freshness and actual MFA enrollment still need integration review.

Generated `apps/api/openapi.json` is the active contract; the older `docs/openapi.json` describes the root reference package only. Validation errors omit input values; responses carry no-store/nosniff headers.

## Database security

Migration 006 introduced creator-or-read-grant SELECT. Migration `011_write_grant_pages.sql` extends SELECT with `actor_has_live_write_grant`. Evidence, claims, documents, and audit reads follow property visibility; read grants do not confer writes. Direct runtime grant INSERT/DELETE and UPDATE are denied. Column-scoped UPDATE grants allow FOR SHARE locks, with mutation policies denying changes.

Only `public.set_property_read_access` / `public.set_property_write_access` / `public.correct_property` mutate grants and corrections. Their trusted migration-owner SECURITY DEFINER context uses fixed `pg_catalog, pg_temp` search_path, schema-qualified relations, explicit actor/tenant/creator/membership checks, parameterized input and atomic audit insertion. PUBLIC execute is revoked; provisioning grants execute only to `oydp_app`.

## Upgrade and rollback

Apply checksum migrations under `infra/db` and re-run runtime provisioning. Do not apply root `migrations/` to the public schema. This is a forward-only security lineage. No destructive down migration is provided for the active tree.

## Validation and boundaries

CI must run the root reference suite and all active API/PostgreSQL tests separately with no skips, plus dependency audit. Active acceptance is the Active API smoke and Active database security workflows. A green Reference foundation checks job is not active-API acceptance.

No production identity enrollment, malware scanner product, independently immutable audit sink, independent security approval, or production release is claimed.
