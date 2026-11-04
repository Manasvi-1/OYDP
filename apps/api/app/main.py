import os
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID
from typing import Literal

import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.auth import verified_subject, require_mfa
from app.pagination import decode_cursor, page_scope, page_result

app = FastAPI(title='OYDP Property Identity API', version='0.5.0')


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
def create_property(payload: PropertyCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, role = access
    if role not in ('owner', 'editor'):
        raise HTTPException(403, 'Property write permission required')
    row = conn.execute("INSERT INTO properties(tenant_id,label,jurisdiction) VALUES (nullif(current_setting('app.tenant_id', true), '')::uuid,%s,%s) RETURNING *",
                        (payload.label, payload.jurisdiction)).fetchone()
    conn.execute("INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type) VALUES (%s,%s,current_setting('app.subject_id'), 'property.created')",
                 (row['tenant_id'], row['id']))
    return row


def readable_property(conn, property_id, creator_only=False):
    # Hold grant locks through the response transaction; revocation waits.
    conn.execute("SELECT 1 FROM property_read_grants WHERE property_id=%s AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE", (property_id,)).fetchall()
    row = conn.execute('SELECT * FROM properties WHERE id=%s', (property_id,)).fetchone()
    if row is None or (creator_only and row['created_by'] != conn.execute("SELECT current_setting('app.subject_id') AS subject").fetchone()['subject']):
        raise HTTPException(404, 'Property not found')
    return row


def cursor_context(conn, kind, cursor, resource=None):
    context = conn.execute("SELECT current_setting('app.tenant_id') AS tenant,current_setting('app.subject_id') AS subject").fetchone()
    scope = page_scope(kind, context['tenant'], context['subject'], resource)
    position = decode_cursor(cursor, scope)
    return scope, position.at if position else None, position.id if position else None


class PropertyPage(BaseModel):
    items: list[PropertyRecord]
    next_cursor: str | None


@app.get('/v1/properties', response_model=PropertyPage)
def list_properties(access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                    cursor: str | None = Query(None, max_length=512)):
    conn, _ = access
    scope, at, record_id = cursor_context(conn, 'properties', cursor)
    # Lock a bounded candidate set of delegated grants before exposing their rows.
    # The explicit CTE predicate supplements RLS, including after lock contention.
    rows = conn.execute("""
      WITH granted AS MATERIALIZED (
        SELECT g.property_id FROM property_read_grants g
        JOIN properties p ON p.tenant_id=g.tenant_id AND p.id=g.property_id
        WHERE NOT g.revoked AND g.expires_at>clock_timestamp()
          AND (%s::timestamptz IS NULL OR (p.created_at,p.id)<(%s::timestamptz,%s::uuid))
        ORDER BY p.created_at DESC,p.id DESC LIMIT %s FOR SHARE OF g
      )
      SELECT p.* FROM properties p
      WHERE (p.created_by=current_setting('app.subject_id') OR p.id IN (SELECT property_id FROM granted))
        AND (%s::timestamptz IS NULL OR (p.created_at,p.id)<(%s::timestamptz,%s::uuid))
      ORDER BY p.created_at DESC,p.id DESC LIMIT %s
      """, (at,at,record_id,limit+1,at,at,record_id,limit+1)).fetchall()
    return page_result(rows, limit, scope, 'created_at')


@app.get('/v1/properties/{property_id}', response_model=PropertyRecord)
def get_property(property_id: UUID, access=Depends(authorized_db, scope='function')):
    return readable_property(access[0], property_id)


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
def share_property(property_id: UUID, payload: ReadAccess, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    return change_read_access(access[0], property_id, payload.recipient_subject, payload.expires_at)


@app.delete('/v1/properties/{property_id}/access', response_model=AccessResult)
def revoke_property(property_id: UUID, payload: Recipient, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    return change_read_access(access[0], property_id, payload.recipient_subject, None)


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    statement: str = Field(min_length=1, max_length=10000)


class ClaimRecord(ClaimCreate):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    created_by: str
    kind: Literal['user_claim']
    verification_status: Literal['unverified']
    recorded_at: datetime


class ClaimPage(BaseModel):
    items: list[ClaimRecord]
    next_cursor: str | None


@app.post('/v1/properties/{property_id}/claims', status_code=201, response_model=ClaimRecord)
def record_claim(property_id: UUID, payload: ClaimCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, role = access
    parent = readable_property(conn, property_id, creator_only=True)
    if role not in ('owner','editor'):
        raise HTTPException(403, 'Property write permission required')
    row = conn.execute("INSERT INTO property_claims(tenant_id,property_id,statement) VALUES(%s,%s,%s) RETURNING *",
                       (parent['tenant_id'],property_id,payload.statement)).fetchone()
    conn.execute("INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type,claim_id) VALUES(%s,%s,current_setting('app.subject_id'),'claim.recorded',%s)",
                 (parent['tenant_id'],property_id,row['id']))
    return row


@app.get('/v1/properties/{property_id}/claims', response_model=ClaimPage)
def list_claims(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25,ge=1,le=100),
                cursor: str | None = Query(None,max_length=512)):
    conn, _ = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'claims', cursor, property_id)
    rows = conn.execute("""SELECT * FROM property_claims WHERE property_id=%s
      AND (%s::timestamptz IS NULL OR (recorded_at,id)<(%s::timestamptz,%s::uuid))
      ORDER BY recorded_at DESC,id DESC LIMIT %s""", (property_id,at,at,record_id,limit+1)).fetchall()
    return page_result(rows,limit,scope,'recorded_at')


def writable_property(conn, role, property_id):
    parent = readable_property(conn, property_id, creator_only=True)
    if role not in ('owner', 'editor'):
        raise HTTPException(403, 'Property write permission required')
    return parent


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    source_class: Literal['user_supplied', 'professional_note', 'published_reference']
    locator: str | None = Field(default=None, min_length=1, max_length=500)


class SourceRecord(SourceCreate):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    created_by: str
    recorded_at: datetime


class SourcePage(BaseModel):
    items: list[SourceRecord]
    next_cursor: str | None


@app.post('/v1/properties/{property_id}/sources', status_code=201, response_model=SourceRecord)
def record_source(property_id: UUID, payload: SourceCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, role = access
    parent = writable_property(conn, role, property_id)
    row = conn.execute("""INSERT INTO evidence_sources(tenant_id,property_id,name,source_class,locator)
      VALUES(%s,%s,%s,%s,%s) RETURNING *""", (parent['tenant_id'], property_id, payload.name, payload.source_class, payload.locator)).fetchone()
    conn.execute("""INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type)
      VALUES(%s,%s,current_setting('app.subject_id'),'source.recorded')""", (parent['tenant_id'], property_id))
    return row


@app.get('/v1/properties/{property_id}/sources', response_model=SourcePage)
def list_sources(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                 cursor: str | None = Query(None, max_length=512)):
    conn, _ = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'sources', cursor, property_id)
    rows = conn.execute("""SELECT * FROM evidence_sources WHERE property_id=%s
      AND (%s::timestamptz IS NULL OR (recorded_at,id)<(%s::timestamptz,%s::uuid))
      ORDER BY recorded_at DESC,id DESC LIMIT %s""", (property_id, at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'recorded_at')


class IdentifierCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    scheme: Literal['local_label', 'survey_number', 'khata', 'municipal_reference']
    identifier_value: str = Field(min_length=1, max_length=200)
    supersede: bool = False


class IdentifierRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    scheme: Literal['local_label', 'survey_number', 'khata', 'municipal_reference']
    identifier_value: str
    created_by: str
    recorded_at: datetime
    superseded_at: datetime | None


class IdentifierPage(BaseModel):
    items: list[IdentifierRecord]
    next_cursor: str | None


@app.post('/v1/properties/{property_id}/identifiers', status_code=201, response_model=IdentifierRecord,
          responses={409: {'description': 'A current identifier already exists for this scheme'}})
def record_identifier(property_id: UUID, payload: IdentifierCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, role = access
    parent = writable_property(conn, role, property_id)
    current = conn.execute("""SELECT id FROM property_identifiers
      WHERE property_id=%s AND scheme=%s AND superseded_at IS NULL FOR UPDATE""", (property_id, payload.scheme)).fetchone()
    if current and not payload.supersede:
        raise HTTPException(409, 'Current identifier exists')
    if current:
        conn.execute('UPDATE property_identifiers SET superseded_at=clock_timestamp() WHERE id=%s', (current['id'],))
        conn.execute("""INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type)
          VALUES(%s,%s,current_setting('app.subject_id'),'identifier.superseded')""", (parent['tenant_id'], property_id))
    try:
        row = conn.execute("""INSERT INTO property_identifiers(tenant_id,property_id,scheme,identifier_value)
          VALUES(%s,%s,%s,%s) RETURNING *""", (parent['tenant_id'], property_id, payload.scheme, payload.identifier_value)).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, 'Current identifier exists') from None
    conn.execute("""INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type)
      VALUES(%s,%s,current_setting('app.subject_id'),'identifier.recorded')""", (parent['tenant_id'], property_id))
    return row


@app.get('/v1/properties/{property_id}/identifiers', response_model=IdentifierPage)
def list_identifiers(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                     cursor: str | None = Query(None, max_length=512)):
    conn, _ = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'identifiers', cursor, property_id)
    rows = conn.execute("""SELECT * FROM property_identifiers WHERE property_id=%s
      AND (%s::timestamptz IS NULL OR (recorded_at,id)<(%s::timestamptz,%s::uuid))
      ORDER BY recorded_at DESC,id DESC LIMIT %s""", (property_id, at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'recorded_at')


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    assertion_type: str = Field(min_length=1, max_length=100)
    assertion_text: str = Field(min_length=1, max_length=10000)
    source_kind: Literal['user_claim', 'professional_review']
    source_id: UUID | None = None
    source_reference: str | None = Field(default=None, min_length=1, max_length=500)
    observed_at: AwareDatetime | None = None


class EvidenceRecord(EvidenceCreate):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    created_by: str | None
    review_status: Literal['unreviewed', 'recorded']
    created_at: datetime


class EvidencePage(BaseModel):
    items: list[EvidenceRecord]
    next_cursor: str | None


@app.post('/v1/properties/{property_id}/evidence', status_code=201, response_model=EvidenceRecord)
def record_evidence(property_id: UUID, payload: EvidenceCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, role = access
    if payload.source_kind == 'professional_review' and not payload.source_reference:
        raise HTTPException(422, 'Invalid request')
    parent = writable_property(conn, role, property_id)
    review = 'recorded' if payload.source_kind == 'professional_review' else 'unreviewed'
    try:
        row = conn.execute("""INSERT INTO evidence_assertions(
          tenant_id,property_id,assertion_type,assertion_text,source_kind,source_reference,observed_at,source_id,review_status)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
          (parent['tenant_id'], property_id, payload.assertion_type, payload.assertion_text, payload.source_kind,
           payload.source_reference, payload.observed_at, payload.source_id, review)).fetchone()
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(422, 'Invalid request') from None
    conn.execute("""INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type)
      VALUES(%s,%s,current_setting('app.subject_id'),'evidence.recorded')""", (parent['tenant_id'], property_id))
    return row


@app.get('/v1/properties/{property_id}/evidence', response_model=EvidencePage)
def list_evidence(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                  cursor: str | None = Query(None, max_length=512)):
    conn, _ = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'evidence', cursor, property_id)
    rows = conn.execute("""SELECT * FROM evidence_assertions WHERE property_id=%s
      AND (%s::timestamptz IS NULL OR (created_at,id)<(%s::timestamptz,%s::uuid))
      ORDER BY created_at DESC,id DESC LIMIT %s""", (property_id, at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'created_at')
