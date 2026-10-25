# Canonical private properties and read access — API 0.3.0

This is the first port of PR #1's private-property access model into the active JWKS API. It does not mount or synchronize the separate root-package schema. Read-only sharing is implemented here; collaborator write delegation and claim APIs remain later work.

## Behavior and API contract

New property records are private to their creator within a verified tenant. Being another tenant member, or even having tenant owner/editor role, does not reveal another creator's record. Explicit non-expired read grants authorize recipients. Membership is checked and locked on every request; grant readers hold a shared grant lock through their transaction. Revocation waits for already-authorized transactions and prevents later reads; already-returned data cannot be retracted.

- POST `/v1/properties`: requires owner/editor membership and a signed access token with `amr` containing `mfa`. `created_by` comes from the verified subject through the transaction context, never client input.
- GET `/v1/properties/{id}`: creator or valid read grant, plus current membership. Forbidden and nonexistent properties both return 404. Output includes attributable `created_by`.
- PUT `/v1/properties/{id}/access`: creator + owner/editor role + MFA; JSON `recipient_subject` and timezone-aware `expires_at`. Recipient must already be a member of the same tenant. Grants expire within 30 days. Exact repeat is idempotent.
- DELETE `/v1/properties/{id}/access`: same authorization; JSON body with `recipient_subject`. Revokes that recipient's read grant; repeated revocation is idempotent. No email or invitation is sent.

Collaborators cannot reshare. Self-sharing, missing recipients, wrong-tenant recipients, invalid expiry and non-MFA sensitive actions are denied. This implements issuer-asserted MFA, not a fresh interactive MFA challenge; provider AMR semantics, auth_time freshness and actual MFA enrollment still need integration review.

Generated `/openapi.json` is the active contract; the older `docs/openapi.json` describes the root reference package only. Validation errors omit input values; responses carry no-store/nosniff headers.

## Database security

Migration 006 changes property SELECT RLS to current membership plus creator or scoped read grant. Evidence reads and audit reads follow property visibility; read grants do not confer evidence writes. Direct runtime grant INSERT/DELETE and UPDATE are denied. Column-scoped UPDATE grants allow FOR SHARE locks, with mutation policies denying changes. Existing generic evidence upload remains absent.

Only `public.set_property_read_access` mutates grants. Its trusted migration-owner SECURITY DEFINER context uses fixed pg_catalog/pg_temp search_path, schema-qualified relations, explicit actor/tenant/creator/membership checks, per-property advisory serialization, recipient/grant locks, parameterized input and atomic audit insertion. PUBLIC execute is revoked; provisioning grants execute only to oydp_app. The migration owner must have the trusted RLS-bypass authority needed for cross-subject recipient lookup. Runtime credentials/settings remain trusted application capabilities, not a defense against arbitrary SQL execution or stolen DB credentials.

Membership deletion cascades grant removal, so re-enrollment does not reactivate an earlier grant. Admin membership operations are separate trusted actions; they do not currently emit the application's sharing audit events. Creator membership removal denies creator access but does not cascade-remove still-valid recipients' separate grants; revoke those explicitly where required by policy.

## Upgrade and rollback

Apply checksum migrations and re-run runtime provisioning before API 0.3.0. Migration 006 attributes old records only from unambiguous property.created audit actors. Records lacking attribution remain inaccessible; a trusted administrator must investigate and explicitly repair them. Never fall back to tenant-wide access. Fresh-database and populated upgrade tests run in disposable CI databases.

This is a forward-only security migration. Rolling the application back to code that assumes tenant-wide access or omits subject context is unsupported. Preserve audit/grant history and use a reviewed forward fix. No destructive down migration is provided.

## Validation and boundaries

CI must run both the root reference suite and all active API/PostgreSQL tests with no skips, plus dependency audit. Tests cover same-tenant denial, grants/revocation/expiry, cross-tenant targets, MFA, audit rollback, direct mutation denial, native lock serialization and populated upgrade attribution.

No UI, provider production configuration, write-grant delegation, claim endpoints, official data integration, documents/scanning/encryption, independently immutable audit sink, independent security approval or production release is claimed.
