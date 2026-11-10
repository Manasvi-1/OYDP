# Property-record access

This controls access to an application record, not legal ownership or title.

The record creator, with an active tenant membership, an unexpired write grant,
and an MFA-authenticated API identity, may share with an existing active member
of the same tenant. Collaborators cannot reshare. Self-targeted changes are denied.

| Operation | Endpoint | Result |
|---|---|---|
| Set or replace access | `PUT /v1/properties/{property_id}/access/{recipient}` | Exact permission set and expiry |
| Revoke access | `DELETE /v1/properties/{property_id}/access/{recipient}` | All recipient permissions revoked |
| Read attributed claims | `GET /v1/properties/{property_id}/claims` | Paginated, explicitly unverified claims |

PUT accepts `actions` (`property:read`, optionally `property:write`) and a
timezone-aware `expires_at`. Expiry must be in the future, within 30 days, and
no later than the creator's current write-grant expiry. An identical request
returns `{"changed": false}` without another audit event. Revocation remains
possible for an inactive recipient. It does not invalidate already returned data.

## Transaction and security boundary

The runtime role cannot directly update grants. A narrowly scoped SECURITY DEFINER
function checks explicit actor, tenant, record creator, membership, expiry, and
permissions. Its owner must be a trusted migration administrator with the required
RLS-bypass authority; never make the API role the function owner. PUBLIC execute is
revoked and search_path is fixed to pg_catalog,pg_temp. Only the restricted runtime
role receives execute. MFA is checked in the authenticated application layer;
database credentials and context remain trusted server inputs.

Access changes serialize per property, lock current membership/controller grants,
and commit recipient grants and an audit outbox event together. Existing grant
read locks delay revocation until those transactions finish. A timeout/failure
rolls back the access change. Ordinary list reads use statement-snapshot semantics.
Audit records include actor, recipient, exact permissions, and expiry. The database
administrator can still alter this outbox; it is not an independent immutable sink.

## Upgrade and rollback

New local databases use the bootstrap script, which applies migrations 001 and 002.
For an existing 001 database, use a trusted administrator to apply only
`migrations/002_property_access.up.sql` once, before deploying API version 0.3.0.
Back up and rehearse against a disposable copy first. Do not rerun bootstrap or
the destructive test harness against real data.

Migration 002 down is allowed only before access audit history exists. Once sharing
events exist, rollback deliberately refuses to discard history; use a reviewed
forward migration. Migration 001 down destroys the whole foundation schema and is
for disposable testing only.

Pending: invitations/member discovery, creator-grant renewal, administrator recovery,
access-management UI, independently delivered audit history, and identity-provider
MFA freshness is enforced on high-risk active-API routes via `auth_time` (default max age 900s) in addition to `amr` methods; live IdP enrollment remains separately verified. Revoking a creator does not cascade to existing recipient grants;
administrators must revoke those separately. No legal authority is conveyed.
