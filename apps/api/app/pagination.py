"""Scoped keyset navigation. Authorization is always enforced separately by RLS."""
import base64
import binascii
import hashlib
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError


class Position(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    v: Literal[1] = 1
    scope: str
    at: AwareDatetime
    id: UUID


def page_scope(kind: str, tenant: str, subject: str, resource: UUID | None = None) -> str:
    # Length-delimited JSON avoids delimiter ambiguities in external subject IDs.
    import json
    return hashlib.sha256(json.dumps([kind, tenant, subject, str(resource) if resource else None],
                                     ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def encode_cursor(scope: str, at: datetime, record_id: UUID) -> str:
    value = Position(scope=scope, at=at, id=record_id).model_dump_json().encode()
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def decode_cursor(token: str | None, scope: str) -> Position | None:
    if token is None:
        return None
    try:
        if not token or len(token) > 512 or '=' in token:
            raise ValueError('Invalid cursor encoding')
        value = base64.b64decode(token + '=' * (-len(token) % 4), altchars=b'-_', validate=True)
        position = Position.model_validate_json(value)
        if position.scope != scope or encode_cursor(position.scope, position.at, position.id) != token:
            raise ValueError('Invalid cursor scope or encoding')
        return position
    except (ValueError, binascii.Error, ValidationError):
        raise HTTPException(422, 'Invalid pagination cursor') from None


def page_result(rows: list[dict], limit: int, scope: str, timestamp: str) -> dict:
    items = rows[:limit]
    cursor = None
    if len(rows) > limit:
        last = items[-1]
        cursor = encode_cursor(scope, last[timestamp], last['id'])
    return {'items': items, 'next_cursor': cursor}
