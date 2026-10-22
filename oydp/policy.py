"""Default-deny property policy; inputs must come from trusted server state."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Action(StrEnum):
    READ = 'property:read'
    WRITE = 'property:write'
    DOWNLOAD = 'evidence:download'


class ScanState(StrEnum):
    QUARANTINED = 'quarantined'
    PASS = 'pass'
    FAIL = 'fail'


@dataclass(frozen=True)
class Principal:
    subject: UUID
    tenant: UUID
    active: bool
    mfa: bool


@dataclass(frozen=True)
class Resource:
    id: UUID
    tenant: UUID
    property_id: UUID
    scan_state: ScanState = ScanState.QUARANTINED


@dataclass(frozen=True)
class Grant:
    subject: UUID
    tenant: UUID
    property_id: UUID
    actions: frozenset[Action]
    expires_at: datetime
    revoked: bool = False
    # Downloads need an explicit document grant, not just a property grant.
    resource_id: UUID | None = None


def authorize(principal: Principal, resource: Resource, action: Action,
              grants: tuple[Grant, ...], *, now: datetime) -> bool:
    """No implicit owner/admin bypass; re-evaluate current grants on every call.

    This policy does not validate JWTs, enforce RLS, or issue download URLs.
    Naive clocks and malformed actions fail closed.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        return False
    if not isinstance(action, Action) or not principal.active:
        return False
    if principal.tenant != resource.tenant:
        return False
    if action in (Action.WRITE, Action.DOWNLOAD) and not principal.mfa:
        return False
    if action == Action.DOWNLOAD and resource.scan_state != ScanState.PASS:
        return False
    for grant in grants:
        if grant.expires_at.tzinfo is None or grant.expires_at.utcoffset() is None:
            continue
        if (grant.subject != principal.subject or grant.tenant != principal.tenant
                or grant.property_id != resource.property_id or grant.revoked
                or grant.expires_at <= now or action not in grant.actions):
            continue
        if grant.resource_id is not None and grant.resource_id != resource.id:
            continue
        if action == Action.DOWNLOAD and grant.resource_id != resource.id:
            continue
        return True
    return False
