import os
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.auth import verified_subject

app = FastAPI(title='OYDP Property Identity API', version='0.2.0')


class PropertyCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    label: str = Field(min_length=1, max_length=200)
    jurisdiction: str = Field(min_length=1, max_length=100)


class PropertyRecord(PropertyCreate):
    id: UUID
    tenant_id: UUID
    created_at: datetime


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
        membership = conn.execute('SELECT role FROM tenant_memberships WHERE tenant_id=%s AND subject_id=%s',
                                  (tenant_id, subject)).fetchone()
        if not membership:
            raise HTTPException(403, 'Tenant membership required')
        yield conn, membership['role']


@app.get('/healthz')
def health():
    return {'status': 'ok'}


@app.post('/v1/properties', status_code=201, response_model=PropertyRecord)
def create_property(payload: PropertyCreate, access=Depends(authorized_db)):
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
    row = conn.execute('SELECT * FROM properties WHERE id=%s', (property_id,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Property not found')
    return row
