import os
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.auth import verified_subject, require_mfa

app = FastAPI(title='OYDP Property Identity API', version='0.3.0')


@app.middleware('http')
async def privacy_headers(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request, exc):
    return JSONResponse(status_code=422, content={'detail':'Invalid request'})



class PropertyCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    label: str = Field(min_length=1, max_length=200)
    jurisdiction: str = Field(min_length=1, max_length=100)


class PropertyRecord(PropertyCreate):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    created_by: str


@contextmanager
def tenant_db(tenant_id: UUID, subject: str):
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise HTTPException(503, 'Database not configured')
    try:
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            with conn.transaction():
                role = conn.execute("SELECT current_user AS name, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
                if role['name'] != 'oydp_app' or role['rolsuper'] or role['rolbypassrls']:
                    raise HTTPException(503, 'Unsafe database runtime role')
                conn.execute("SELECT set_config('statement_timeout', '5000', true)")
                conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
                conn.execute("SELECT set_config('app.subject_id', %s, true)", (subject,))
                yield conn
    except psycopg.Error:
        raise HTTPException(503, 'Database operation unavailable') from None


def authorized_db(tenant_id: UUID = Header(alias='X-Tenant-ID'), subject: str = Depends(verified_subject)):
    with tenant_db(tenant_id, subject) as conn:
        membership = conn.execute('SELECT role FROM tenant_memberships WHERE tenant_id=%s AND subject_id=%s FOR SHARE',
                                  (tenant_id, subject)).fetchone()
        if not membership:
            raise HTTPException(403, 'Tenant membership required')
        yield conn, membership['role']


@app.get('/healthz')
def health():
    return {'status': 'ok'}


@app.post('/v1/properties', status_code=201, response_model=PropertyRecord)
def create_property(payload: PropertyCreate, access=Depends(authorized_db), mfa=Depends(require_mfa)):
    conn, role = access
    if role not in ('owner', 'editor'):
        raise HTTPException(403, 'Property write permission required')
    row = conn.execute("INSERT INTO properties(tenant_id,label,jurisdiction) VALUES (nullif(current_setting('app.tenant_id', true), '')::uuid,%s,%s) RETURNING *",
                        (payload.label, payload.jurisdiction)).fetchone()
    conn.execute("INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type) VALUES (%s,%s,current_setting('app.subject_id'), 'property.created')",
                 (row['tenant_id'], row['id']))
    return row


@app.get('/v1/properties/{property_id}', response_model=PropertyRecord)
def get_property(property_id: UUID, access=Depends(authorized_db)):
    conn, _ = access
    # Hold a shared grant lock through the response transaction so revocation
    # serializes with in-flight granted reads. Creators need no delegated grant.
    conn.execute("SELECT 1 FROM property_read_grants WHERE property_id=%s AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE", (property_id,)).fetchall()
    row = conn.execute('SELECT * FROM properties WHERE id=%s', (property_id,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Property not found')
    return row


class Recipient(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    recipient_subject: str = Field(min_length=1, max_length=255)


class ReadAccess(Recipient):
    expires_at: AwareDatetime


class AccessResult(BaseModel):
    changed: bool


def change_read_access(conn, property_id, recipient, expiry):
    try:
        return conn.execute("SELECT public.set_property_read_access(nullif(current_setting('app.tenant_id',true),'')::uuid,%s,%s,%s) AS changed",
                            (property_id, recipient, expiry)).fetchone()
    except psycopg.errors.NoDataFound:
        raise HTTPException(404, 'Property or recipient unavailable') from None
    except psycopg.errors.InvalidParameterValue:
        raise HTTPException(422, 'Expiry must be in the next 30 days') from None


@app.put('/v1/properties/{property_id}/access', response_model=AccessResult)
def share_property(property_id: UUID, payload: ReadAccess, access=Depends(authorized_db), mfa=Depends(require_mfa)):
    return change_read_access(access[0], property_id, payload.recipient_subject, payload.expires_at)


@app.delete('/v1/properties/{property_id}/access', response_model=AccessResult)
def revoke_property(property_id: UUID, payload: Recipient, access=Depends(authorized_db), mfa=Depends(require_mfa)):
    return change_read_access(access[0], property_id, payload.recipient_subject, None)
