import os
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from uuid import UUID, uuid4
from typing import Literal

import anyio
import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.auth import assert_mfa_configuration, verified_subject, require_mfa
from app.documents import (
    DocumentRejected, ScannerUnavailable, StorageUnavailable, aad_for, authenticated_plaintext,
    digest_bytes, gate_download, get_document_scanner, inspect_upload, read_limited,
    reject_declared_length, scan_outcome, seal, storage_key,
)
from app.pagination import decode_cursor, page_scope, page_result


@asynccontextmanager
async def lifespan(_app: FastAPI):
    assert_mfa_configuration()
    yield


app = FastAPI(title='OYDP Property Identity API', version='0.11.0', lifespan=lifespan)


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


class PropertyCorrection(BaseModel):
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


def current_subject(conn):
    return conn.execute("SELECT current_setting('app.subject_id') AS subject").fetchone()['subject']


def readable_property(conn, property_id, creator_only=False):
    # Hold grant locks through the response transaction; revocation waits.
    conn.execute("SELECT 1 FROM property_read_grants WHERE property_id=%s AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE", (property_id,)).fetchall()
    row = conn.execute('SELECT * FROM properties WHERE id=%s', (property_id,)).fetchone()
    if row is None or (creator_only and row['created_by'] != current_subject(conn)):
        raise HTTPException(404, 'Property not found')
    return row


def writable_property(conn, property_id):
    row = readable_property(conn, property_id)
    subject = current_subject(conn)
    if row['created_by'] == subject:
        return row
    grant = conn.execute("""SELECT 1 FROM property_write_grants WHERE property_id=%s AND subject_id=%s
      AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE""", (property_id, subject)).fetchone()
    if grant is None:
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


def call_guarded(conn, statement, params, invalid_message):
    try:
        return conn.execute(statement, params).fetchone()
    except psycopg.errors.NoDataFound:
        raise HTTPException(404, 'Property or recipient unavailable') from None
    except psycopg.errors.InvalidParameterValue:
        raise HTTPException(422, invalid_message) from None


def change_read_access(conn, property_id, recipient, expiry):
    return call_guarded(conn, "SELECT public.set_property_read_access(nullif(current_setting('app.tenant_id',true),'')::uuid,%s,%s,%s) AS changed",
                        (property_id, recipient, expiry), 'Expiry must be in the next 30 days')


@app.put('/v1/properties/{property_id}/access', response_model=AccessResult)
def share_property(property_id: UUID, payload: ReadAccess, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    return change_read_access(access[0], property_id, payload.recipient_subject, payload.expires_at)


@app.delete('/v1/properties/{property_id}/access', response_model=AccessResult)
def revoke_property(property_id: UUID, payload: Recipient, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    return change_read_access(access[0], property_id, payload.recipient_subject, None)


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    statement: str = Field(min_length=1, max_length=10000)
    source_id: UUID | None = None


class ClaimRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    created_by: str
    statement: str
    kind: Literal['user_claim']
    verification_status: Literal['unverified']
    source_id: UUID | None
    recorded_at: datetime


class ClaimPage(BaseModel):
    items: list[ClaimRecord]
    next_cursor: str | None


@app.post('/v1/properties/{property_id}/claims', status_code=201, response_model=ClaimRecord)
def record_claim(property_id: UUID, payload: ClaimCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, role = access
    # Property-scoped denial stays 404; tenant role denial is 403 after visibility.
    writable_property(conn, property_id)
    require_writer_role(role)
    return call_trusted(
        conn,
        f"""SELECT id, tenant_id, property_id, created_by, statement, kind, verification_status, source_id, recorded_at
          FROM public.record_property_claim({_TENANT}, %s, %s, %s)""",
        (property_id, payload.statement, payload.source_id),
    )


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


class CorrectionResult(PropertyRecord):
    changed: bool


class CorrectionRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    previous_label: str
    previous_jurisdiction: str
    label: str
    jurisdiction: str
    actor_subject: str
    recorded_at: datetime


class CorrectionPage(BaseModel):
    items: list[CorrectionRecord]
    next_cursor: str | None


class WriteGrantRecord(BaseModel):
    recipient_subject: str
    expires_at: datetime
    revoked: bool


class WriteGrantPage(BaseModel):
    items: list[WriteGrantRecord]
    next_cursor: str | None


def require_writer_role(role):
    if role not in ('owner', 'editor'):
        raise HTTPException(403, 'Property write permission required')


@app.patch('/v1/properties/{property_id}', response_model=CorrectionResult)
def correct_property(property_id: UUID, payload: PropertyCorrection, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    """Correct one property's label and jurisdiction.

    The actor is the creator, or a current delegated writer, and holds an owner or editor role.
    Another property record is not merged or deleted.
    """
    conn, role = access
    writable_property(conn, property_id)
    require_writer_role(role)
    changed = call_guarded(conn, "SELECT public.correct_property(nullif(current_setting('app.tenant_id',true),'')::uuid,%s,%s,%s) AS changed",
                           (property_id, payload.label, payload.jurisdiction), 'Invalid property correction')
    current = readable_property(conn, property_id)
    return {**current, 'changed': changed['changed']}


@app.get('/v1/properties/{property_id}/corrections', response_model=CorrectionPage)
def list_corrections(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                     cursor: str | None = Query(None, max_length=512)):
    conn, _ = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'corrections', cursor, property_id)
    rows = conn.execute("""SELECT id,tenant_id,property_id,previous_label,previous_jurisdiction,label,jurisdiction,actor_subject,recorded_at
      FROM property_corrections WHERE property_id=%s
      AND tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
      AND (%s::timestamptz IS NULL OR (recorded_at,id)<(%s::timestamptz,%s::uuid))
      ORDER BY recorded_at DESC,id DESC LIMIT %s""", (property_id, at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'recorded_at')


def change_write_access(conn, property_id, recipient, expiry):
    return call_guarded(conn, "SELECT public.set_property_write_access(nullif(current_setting('app.tenant_id',true),'')::uuid,%s,%s,%s) AS changed",
                        (property_id, recipient, expiry), 'Expiry must be in the next 30 days')


@app.get('/v1/properties/{property_id}/writers', response_model=WriteGrantPage)
def list_writers(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                 cursor: str | None = Query(None, max_length=512)):
    conn, _ = access
    row = readable_property(conn, property_id)
    subject = current_subject(conn)
    scope, at, record_id = cursor_context(conn, 'writers', cursor, property_id)
    creator = row['created_by'] == subject
    rows = conn.execute("""SELECT id,subject_id AS recipient_subject,expires_at,revoked FROM property_write_grants
      WHERE property_id=%s AND tenant_id=nullif(current_setting('app.tenant_id', true), '')::uuid
        AND (%s OR subject_id=%s)
        AND (%s::timestamptz IS NULL OR (expires_at,id)<(%s::timestamptz,%s::uuid))
      ORDER BY expires_at DESC,id DESC LIMIT %s""",
                        (property_id, creator, subject, at, at, record_id, limit + 1)).fetchall()
    if not creator and not rows:
        raise HTTPException(404, 'Property not found')
    return page_result(rows, limit, scope, 'expires_at')


@app.put('/v1/properties/{property_id}/writers', response_model=AccessResult)
def grant_writer(property_id: UUID, payload: ReadAccess, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    return change_write_access(access[0], property_id, payload.recipient_subject, payload.expires_at)


@app.delete('/v1/properties/{property_id}/writers', response_model=AccessResult)
def revoke_writer(property_id: UUID, payload: Recipient, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    return change_write_access(access[0], property_id, payload.recipient_subject, None)


class DocumentRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    created_by: str
    media_type: Literal['application/pdf', 'image/png', 'image/jpeg']
    byte_size: int
    sha256: str = Field(min_length=64, max_length=64)
    scan_state: Literal['quarantined', 'pass', 'fail']
    created_at: datetime
    scanned_at: datetime | None
    claim_id: UUID | None = None
    source_id: UUID | None = None
    identifier_id: UUID | None = None


class DocumentAttribution(BaseModel):
    model_config = ConfigDict(extra='forbid')
    claim_id: UUID | None = None
    source_id: UUID | None = None
    identifier_id: UUID | None = None


_DOCUMENT_META = (
    'id,tenant_id,property_id,created_by,media_type,byte_size,sha256,scan_state,'
    'created_at,scanned_at,claim_id,source_id,identifier_id'
)


def document_db_error(exc):
    if isinstance(exc, psycopg.errors.NoDataFound):
        raise HTTPException(404, 'Document not found') from None
    if isinstance(exc, psycopg.errors.InsufficientPrivilege):
        raise HTTPException(403, 'Document is not available') from None
    if isinstance(exc, psycopg.errors.InvalidParameterValue):
        raise HTTPException(409, 'Document scan already decided') from None
    if isinstance(exc, psycopg.errors.ObjectNotInPrerequisiteState):
        raise HTTPException(503, 'Document scanner unavailable') from None
    raise exc


def document_view(row):
    return {**row, 'sha256': bytes(row['sha256']).hex()}


def document_meta(conn, property_id, document_id):
    row = conn.execute(f'SELECT {_DOCUMENT_META} FROM property_documents WHERE property_id=%s AND id=%s',
                       (property_id, document_id)).fetchone()
    if row is None:
        raise HTTPException(404, 'Document not found')
    return row


def assert_document_writer(tenant_id, subject, property_id):
    with tenant_db(tenant_id, subject) as conn:
        membership = conn.execute('SELECT role FROM tenant_memberships WHERE tenant_id=%s AND subject_id=%s FOR SHARE',
                                  (tenant_id, subject)).fetchone()
        if not membership:
            raise HTTPException(403, 'Tenant membership required')
        writable_property(conn, property_id)
        require_writer_role(membership['role'])


def quarantine_document(tenant_id, subject, property_id, payload, media, key):
    """Encrypt and store before any scan or download. The client cannot choose scan_state."""
    document_id = uuid4()
    with tenant_db(tenant_id, subject) as conn:
        membership = conn.execute('SELECT role FROM tenant_memberships WHERE tenant_id=%s AND subject_id=%s FOR SHARE',
                                  (tenant_id, subject)).fetchone()
        if not membership:
            raise HTTPException(403, 'Tenant membership required')
        parent = writable_property(conn, property_id)
        require_writer_role(membership['role'])
        nonce, ciphertext = seal(key, payload, aad_for(parent['tenant_id'], property_id, document_id, media))
        row = conn.execute(f"""INSERT INTO property_documents
          (id,tenant_id,property_id,created_by,media_type,byte_size,sha256,scan_state,ciphertext,nonce)
          VALUES (%s,%s,%s,current_setting('app.subject_id'),%s,%s,%s,'quarantined',%s,%s)
          RETURNING {_DOCUMENT_META}""",
          (document_id, parent['tenant_id'], property_id, media, len(payload), digest_bytes(payload), ciphertext, nonce)).fetchone()
        conn.execute("""INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type,document_id)
          VALUES (%s,%s,current_setting('app.subject_id'),'document.quarantined',%s)""",
          (parent['tenant_id'], property_id, document_id))
    return document_view(row)


@app.post('/v1/properties/{property_id}/documents', status_code=201, response_model=DocumentRecord)
async def upload_document(property_id: UUID, request: Request, tenant_id: UUID = Header(alias='X-Tenant-ID'),
                          subject: str = Depends(verified_subject), mfa=Depends(require_mfa)):
    """Quarantine one synthetic file. Nothing in the request can mark it clean."""
    await anyio.to_thread.run_sync(lambda: assert_document_writer(tenant_id, subject, property_id))
    try:
        reject_declared_length(request.headers.get('content-length'))
        payload = await read_limited(request)
        media = inspect_upload(request.headers.get('content-type'), payload)
        key = storage_key()
    except DocumentRejected as exc:
        raise HTTPException(exc.status_code, exc.detail) from None
    except StorageUnavailable:
        raise HTTPException(503, 'Document storage not configured') from None
    return await anyio.to_thread.run_sync(lambda: quarantine_document(tenant_id, subject, property_id, payload, media, key))


@app.get('/v1/properties/{property_id}/documents/{document_id}', response_model=DocumentRecord)
def get_document(property_id: UUID, document_id: UUID, access=Depends(authorized_db, scope='function')):
    conn, _role = access
    readable_property(conn, property_id)
    return document_view(document_meta(conn, property_id, document_id))


@app.put('/v1/properties/{property_id}/documents/{document_id}/attribution', response_model=DocumentRecord)
def attribute_document(property_id: UUID, document_id: UUID, payload: DocumentAttribution,
                       access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    """Link a quarantined document to an unverified claim, live source, and/or current identifier.

    Attribution does not change claim verification, source rights, identifier status, or scan_state.
    Export packets include these refs and still set title_verified false.
    """
    conn, role = access
    writable_property(conn, property_id)
    require_writer_role(role)
    if payload.claim_id is None and payload.source_id is None and payload.identifier_id is None:
        raise HTTPException(422, 'Invalid attribution')
    row = call_trusted(
        conn,
        f"""SELECT id, tenant_id, property_id, created_by, media_type, byte_size, sha256, scan_state,
              created_at, scanned_at, claim_id, source_id, identifier_id
            FROM public.attribute_property_document({_TENANT}, %s, %s, %s, %s, %s)""",
        (property_id, document_id, payload.claim_id, payload.source_id, payload.identifier_id),
    )
    return document_view(row)


@app.post('/v1/properties/{property_id}/documents/{document_id}/scan', response_model=DocumentRecord)
def scan_document(property_id: UUID, document_id: UUID, access=Depends(authorized_db, scope='function'),
                  mfa=Depends(require_mfa), scanner=Depends(get_document_scanner)):
    """Ask the configured scanner. An absent scanner leaves the file quarantined."""
    conn, role = access
    parent = writable_property(conn, property_id)
    require_writer_role(role)
    current = document_meta(conn, property_id, document_id)
    if current['scan_state'] != 'quarantined':
        raise HTTPException(409, 'Document scan already decided')
    if scanner is None:
        raise HTTPException(503, 'Document scanner unavailable')
    try:
        sealed = conn.execute("""SELECT ciphertext,nonce,media_type,sha256,byte_size
          FROM public.load_quarantined_document(%s,%s,%s)""",
          (parent['tenant_id'], property_id, document_id)).fetchone()
    except psycopg.Error as exc:
        document_db_error(exc)
    try:
        plain = authenticated_plaintext(
            storage_key(), sealed['nonce'], sealed['ciphertext'],
            aad_for(parent['tenant_id'], property_id, document_id, sealed['media_type']),
            sealed['media_type'], sealed['byte_size'], sealed['sha256'])
        outcome = scan_outcome(scanner, plain, sealed['media_type'])
    except (DocumentRejected, StorageUnavailable, ScannerUnavailable):
        raise HTTPException(503, 'Document scanner unavailable') from None
    if outcome == 'pass':
        conn.execute("SELECT set_config('app.document_scanner', 'configured', true)")
    try:
        conn.execute('SELECT public.record_document_scan(%s,%s,%s,%s,%s)',
                     (parent['tenant_id'], property_id, document_id, outcome, bytes(sealed['sha256'])))
    except psycopg.Error as exc:
        document_db_error(exc)
    return document_view(document_meta(conn, property_id, document_id))


@app.get('/v1/properties/{property_id}/documents/{document_id}/content')
def download_document(property_id: UUID, document_id: UUID, access=Depends(authorized_db, scope='function'),
                      mfa=Depends(require_mfa)):
    """Release bytes only after a clean scan. Quarantined and failed files are refused."""
    conn, _role = access
    parent = readable_property(conn, property_id)
    current = document_meta(conn, property_id, document_id)
    try:
        gate_download(current['scan_state'])
    except DocumentRejected as exc:
        raise HTTPException(exc.status_code, exc.detail) from None
    try:
        sealed = conn.execute("""SELECT ciphertext,nonce,media_type,sha256,byte_size
          FROM public.load_document_ciphertext(%s,%s,%s)""",
          (parent['tenant_id'], property_id, document_id)).fetchone()
    except psycopg.Error as exc:
        document_db_error(exc)
    try:
        plain = authenticated_plaintext(
            storage_key(), sealed['nonce'], sealed['ciphertext'],
            aad_for(parent['tenant_id'], property_id, document_id, sealed['media_type']),
            sealed['media_type'], sealed['byte_size'], sealed['sha256'])
    except (DocumentRejected, StorageUnavailable):
        raise HTTPException(503, 'Document is not available') from None
    return Response(content=plain, media_type=sealed['media_type'],
                    headers={'Content-Disposition': 'attachment; filename="document"'})


# Trusted evidence. SQL functions decide who may write. A review never changes a claim's verification.
PACKET_NOTICE = 'This packet is not a title certificate. Claims remain unverified, and a professional review is not title.'
_PACKET_CAP = 100
_TRUSTED_SQL = {
    'Export consent required': (403, 'Export consent required'),
    'Source is withdrawn': (422, 'Source is withdrawn'),
    'Identifier resolution required': (422, 'Identifier resolution required'),
    'Invalid identifier': (422, 'Invalid identifier'),
    'Invalid source': (422, 'Invalid source'),
    'Invalid review': (422, 'Invalid review'),
    'Invalid claim': (422, 'Invalid claim'),
    'Invalid attribution': (422, 'Invalid attribution'),
    'Invalid request': (422, 'Invalid request'),
    'Document not found': (404, 'Document not found'),
}
_TENANT = "nullif(current_setting('app.tenant_id', true), '')::uuid"


def trusted_http_error(exc):
    """Map an allowlisted database refusal. Every other failure stays generic."""
    if getattr(exc, 'sqlstate', None) == 'P0002':
        return HTTPException(404, 'Not found')
    primary = ''
    diag = getattr(exc, 'diag', None)
    if diag is not None and diag.message_primary:
        primary = str(diag.message_primary).strip()
    mapped = _TRUSTED_SQL.get(primary)
    if mapped is not None:
        return HTTPException(mapped[0], mapped[1])
    return HTTPException(503, 'Database operation unavailable')


def call_trusted(conn, statement, params):
    try:
        row = conn.execute(statement, params).fetchone()
    except psycopg.Error as exc:
        raise trusted_http_error(exc) from None
    if row is None:
        raise HTTPException(503, 'Database operation unavailable')
    return row


def creator_gate(conn, property_id, role):
    """Consent and export belong to the creator, and only while that creator can still write."""
    row = readable_property(conn, property_id)
    if row['created_by'] != current_subject(conn):
        raise HTTPException(404, 'Property not found')
    require_writer_role(role)
    return row


class IdentifierCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    scheme: Literal['internal', 'survey', 'municipal', 'khata']
    identifier_value: str = Field(min_length=1, max_length=120)
    resolution: Literal['supersede', 'conflict'] | None = None


class IdentifierRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    scheme: Literal['internal', 'survey', 'municipal', 'khata']
    identifier_value: str
    version: int
    status: Literal['current', 'superseded', 'conflict']
    recorded_by: str
    recorded_at: datetime


class IdentifierResult(IdentifierRecord):
    changed: bool


class IdentifierPage(BaseModel):
    items: list[IdentifierRecord]
    next_cursor: str | None


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    origin: Literal['user_supplied', 'professional', 'published_notice']
    jurisdiction: str = Field(min_length=1, max_length=100)


class SourceRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    origin: Literal['user_supplied', 'professional', 'published_notice']
    jurisdiction: str
    rights_status: Literal['unknown']
    created_by: str
    created_at: datetime
    withdrawn_at: datetime | None
    withdrawal_reason: str | None


class SourcePage(BaseModel):
    items: list[SourceRecord]
    next_cursor: str | None


class SourceWithdrawal(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=500)


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    disposition: Literal['recorded', 'abstained']
    statement: str = Field(min_length=1, max_length=2000)
    source_id: UUID | None = None


class ReviewRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    reviewer_subject: str
    disposition: Literal['recorded', 'abstained']
    statement: str
    source_id: UUID | None
    recorded_at: datetime
    title_effect: Literal['none']


class ReviewPage(BaseModel):
    items: list[ReviewRecord]
    next_cursor: str | None


class ConsentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    purpose: Literal['passport_export']


class ConsentRecord(BaseModel):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    subject_id: str
    purpose: Literal['passport_export']
    granted_at: datetime
    revoked_at: datetime | None
    changed: bool


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PacketClaim(BaseModel):
    id: UUID
    statement: str
    created_by: str
    kind: Literal['user_claim']
    verification_status: Literal['unverified']
    source_id: UUID | None
    recorded_at: datetime


class EvidencePacket(BaseModel):
    property_id: UUID
    title_verified: Literal[False]
    notice: Literal[PACKET_NOTICE]
    claims: list[PacketClaim]
    identifiers: list[IdentifierRecord]
    reviews: list[ReviewRecord]
    documents: list[DocumentRecord]


class AuditRecord(BaseModel):
    event_type: Literal[
        'property.created', 'access.granted', 'access.revoked', 'claim.recorded', 'property.corrected',
        'write.granted', 'write.revoked', 'document.quarantined', 'document.scan_passed', 'document.scan_failed',
        'document.attributed',
        'identifier.recorded', 'identifier.conflict', 'review.recorded', 'consent.recorded', 'consent.revoked',
        'packet.exported', 'diligence.opened', 'diligence.noted', 'diligence.closed',
    ]
    actor_subject: str
    recorded_at: datetime
    delivered_at: datetime


class AuditPage(BaseModel):
    items: list[AuditRecord]
    next_cursor: str | None


class DocumentPage(BaseModel):
    items: list[DocumentRecord]
    next_cursor: str | None


def present_review(row):
    return {**row, 'title_effect': 'none'}


def packet_rows(conn, statement, params):
    rows = conn.execute(statement, (*params, _PACKET_CAP + 1)).fetchall()
    if len(rows) > _PACKET_CAP:
        raise HTTPException(422, 'Export packet is too large')
    return rows


@app.post('/v1/properties/{property_id}/identifiers', response_model=IdentifierResult)
def record_identifier(property_id: UUID, payload: IdentifierCreate, access=Depends(authorized_db, scope='function'),
                      mfa=Depends(require_mfa)):
    """Record one identifier. The same value is unchanged. A different value needs supersede or conflict."""
    conn, role = access
    writable_property(conn, property_id)
    require_writer_role(role)
    return call_trusted(conn, f"""SELECT * FROM public.record_property_identifier({_TENANT}, %s, %s, %s, %s)""",
                        (property_id, payload.scheme, payload.identifier_value, payload.resolution))


@app.get('/v1/properties/{property_id}/identifiers', response_model=IdentifierPage)
def list_identifiers(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                     cursor: str | None = Query(None, max_length=512)):
    conn, _role = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'identifiers', cursor, property_id)
    rows = conn.execute(f"""SELECT id, tenant_id, property_id, scheme, identifier_value, version, status, recorded_by, recorded_at
      FROM property_identifiers
      WHERE property_id=%s AND tenant_id={_TENANT}
        AND (%s::timestamptz IS NULL OR (recorded_at, id)<(%s::timestamptz, %s::uuid))
      ORDER BY recorded_at DESC, id DESC LIMIT %s""",
                        (property_id, at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'recorded_at')


@app.post('/v1/sources', status_code=201, response_model=SourceRecord)
def register_source(payload: SourceCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    """Register a source. The caller cannot choose rights_status; the database keeps it unknown."""
    conn, role = access
    require_writer_role(role)
    return call_trusted(conn, f"""SELECT * FROM public.register_evidence_source({_TENANT}, %s, %s, %s)""",
                        (payload.name, payload.origin, payload.jurisdiction))


@app.get('/v1/sources', response_model=SourcePage)
def list_sources(access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                 cursor: str | None = Query(None, max_length=512)):
    conn, _role = access
    scope, at, record_id = cursor_context(conn, 'sources', cursor)
    rows = conn.execute(f"""SELECT id, tenant_id, name, origin, jurisdiction, rights_status, created_by, created_at,
        withdrawn_at, withdrawal_reason
      FROM evidence_sources
      WHERE tenant_id={_TENANT}
        AND (%s::timestamptz IS NULL OR (created_at, id)<(%s::timestamptz, %s::uuid))
      ORDER BY created_at DESC, id DESC LIMIT %s""",
                        (at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'created_at')


@app.post('/v1/sources/{source_id}/withdrawal', response_model=AccessResult)
def withdraw_source(source_id: UUID, payload: SourceWithdrawal, access=Depends(authorized_db, scope='function'),
                    mfa=Depends(require_mfa)):
    conn, role = access
    require_writer_role(role)
    return call_trusted(conn, f"""SELECT public.withdraw_evidence_source({_TENANT}, %s, %s) AS changed""",
                        (source_id, payload.reason))


@app.post('/v1/properties/{property_id}/reviews', status_code=201, response_model=ReviewRecord)
def record_review(property_id: UUID, payload: ReviewCreate, access=Depends(authorized_db, scope='function'),
                  mfa=Depends(require_mfa)):
    """Store a review. Disposition is recorded or abstained, and title_effect stays none."""
    conn, role = access
    writable_property(conn, property_id)
    require_writer_role(role)
    row = call_trusted(conn, f"""SELECT * FROM public.record_professional_review({_TENANT}, %s, %s, %s, %s)""",
                       (property_id, payload.disposition, payload.statement, payload.source_id))
    return present_review(row)


@app.get('/v1/properties/{property_id}/reviews', response_model=ReviewPage)
def list_reviews(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                 cursor: str | None = Query(None, max_length=512)):
    conn, _role = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'reviews', cursor, property_id)
    rows = conn.execute(f"""SELECT id, tenant_id, property_id, reviewer_subject, disposition, statement, source_id, recorded_at
      FROM professional_reviews
      WHERE property_id=%s AND tenant_id={_TENANT}
        AND (%s::timestamptz IS NULL OR (recorded_at, id)<(%s::timestamptz, %s::uuid))
      ORDER BY recorded_at DESC, id DESC LIMIT %s""",
                        (property_id, at, at, record_id, limit + 1)).fetchall()
    page = page_result(rows, limit, scope, 'recorded_at')
    page['items'] = [present_review(row) for row in page['items']]
    return page


@app.post('/v1/properties/{property_id}/consents', response_model=ConsentRecord)
def grant_consent(property_id: UUID, payload: ConsentCreate, access=Depends(authorized_db, scope='function'),
                  mfa=Depends(require_mfa)):
    conn, role = access
    creator_gate(conn, property_id, role)
    return call_trusted(conn, f"""SELECT * FROM public.record_property_consent({_TENANT}, %s, %s)""",
                        (property_id, payload.purpose))


@app.delete('/v1/properties/{property_id}/consents', response_model=AccessResult)
def revoke_consent(property_id: UUID, payload: ConsentCreate, access=Depends(authorized_db, scope='function'),
                   mfa=Depends(require_mfa)):
    conn, role = access
    creator_gate(conn, property_id, role)
    return call_trusted(conn, f"""SELECT public.revoke_property_consent({_TENANT}, %s, %s) AS changed""",
                        (property_id, payload.purpose))


@app.post('/v1/properties/{property_id}/exports', response_model=EvidencePacket)
def export_property(property_id: UUID, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa),
                    payload: ExportRequest | None = None):
    """Build the caller's packet only after the database records a live creator consent."""
    del payload
    conn, role = access
    creator_gate(conn, property_id, role)
    try:
        conn.execute(f"SELECT public.authorize_property_export({_TENANT}, %s)", (property_id,)).fetchone()
    except psycopg.Error as exc:
        raise trusted_http_error(exc) from None
    claims = packet_rows(conn, f"""SELECT id, statement, created_by, kind, verification_status, source_id, recorded_at
      FROM property_claims
      WHERE property_id=%s AND tenant_id={_TENANT}
      ORDER BY recorded_at DESC, id DESC LIMIT %s""", (property_id,))
    for claim in claims:
        if claim['kind'] != 'user_claim' or claim['verification_status'] != 'unverified':
            raise HTTPException(503, 'Database operation unavailable')
    identifiers = packet_rows(conn, f"""SELECT id, tenant_id, property_id, scheme, identifier_value, version, status,
        recorded_by, recorded_at
      FROM property_identifiers
      WHERE property_id=%s AND tenant_id={_TENANT}
      ORDER BY recorded_at DESC, id DESC LIMIT %s""", (property_id,))
    reviews = [present_review(row) for row in packet_rows(conn, f"""SELECT id, tenant_id, property_id, reviewer_subject,
        disposition, statement, source_id, recorded_at
      FROM professional_reviews
      WHERE property_id=%s AND tenant_id={_TENANT}
      ORDER BY recorded_at DESC, id DESC LIMIT %s""", (property_id,))]
    documents = [document_view(row) for row in packet_rows(conn, f"""SELECT {_DOCUMENT_META}
      FROM property_documents
      WHERE property_id=%s AND tenant_id={_TENANT}
      ORDER BY created_at DESC, id DESC LIMIT %s""", (property_id,))]
    for document in documents:
        document.pop('ciphertext', None)
        document.pop('nonce', None)
    return {
        'property_id': property_id,
        'title_verified': False,
        'notice': PACKET_NOTICE,
        'claims': claims,
        'identifiers': identifiers,
        'reviews': reviews,
        'documents': documents,
    }


@app.get('/v1/properties/{property_id}/documents', response_model=DocumentPage)
def list_documents(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                   cursor: str | None = Query(None, max_length=512)):
    """Metadata only. Ciphertext stays in the database and is not selected."""
    conn, _role = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'documents', cursor, property_id)
    rows = conn.execute(f"""SELECT {_DOCUMENT_META} FROM property_documents
      WHERE property_id=%s AND tenant_id={_TENANT}
        AND (%s::timestamptz IS NULL OR (created_at, id)<(%s::timestamptz, %s::uuid))
      ORDER BY created_at DESC, id DESC LIMIT %s""",
                        (property_id, at, at, record_id, limit + 1)).fetchall()
    page = page_result(rows, limit, scope, 'created_at')
    page['items'] = [document_view(row) for row in page['items']]
    return page


@app.get('/v1/properties/{property_id}/audit', response_model=AuditPage)
def list_property_audit(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                        cursor: str | None = Query(None, max_length=512)):
    """Delivered ledger rows for one visible property. The response has no claim text or document bytes."""
    conn, _role = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'audit', cursor, property_id)
    rows = conn.execute(f"""SELECT id, event_type, actor_subject, recorded_at, delivered_at
      FROM audit_ledger
      WHERE property_id=%s AND tenant_id={_TENANT}
        AND (%s::timestamptz IS NULL OR (recorded_at, id)<(%s::timestamptz, %s::uuid))
      ORDER BY recorded_at DESC, id DESC LIMIT %s""",
                        (property_id, at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'recorded_at')


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)


class RequestRecord(RequestCreate):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    created_by: str
    status: Literal['open', 'closed']
    created_at: datetime
    closed_at: datetime | None


class RequestPage(BaseModel):
    items: list[RequestRecord]
    next_cursor: str | None


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    body: str = Field(min_length=1, max_length=10000)


class NoteRecord(NoteCreate):
    id: UUID
    tenant_id: UUID
    property_id: UUID
    request_id: UUID
    created_by: str
    created_at: datetime


class NotePage(BaseModel):
    items: list[NoteRecord]
    next_cursor: str | None


def audit_diligence(conn, tenant_id, property_id, event_type):
    conn.execute("""INSERT INTO property_audit_events(tenant_id,property_id,actor_subject,event_type)
      VALUES(%s,%s,current_setting('app.subject_id'),%s)""", (tenant_id, property_id, event_type))


@app.post('/v1/properties/{property_id}/requests', status_code=201, response_model=RequestRecord)
def open_request(property_id: UUID, payload: RequestCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, _role = access
    parent = writable_property(conn, property_id)
    try:
        row = conn.execute("""INSERT INTO diligence_requests(tenant_id,property_id,title,body)
          VALUES(%s,%s,%s,%s) RETURNING *""", (parent['tenant_id'], property_id, payload.title, payload.body)).fetchone()
    except (psycopg.errors.InsufficientPrivilege, psycopg.errors.ForeignKeyViolation):
        raise HTTPException(404, 'Property not found') from None
    audit_diligence(conn, parent['tenant_id'], property_id, 'diligence.opened')
    return row


@app.get('/v1/properties/{property_id}/requests', response_model=RequestPage)
def list_requests(property_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
                  cursor: str | None = Query(None, max_length=512)):
    conn, _role = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'requests', cursor, property_id)
    rows = conn.execute(f"""SELECT * FROM diligence_requests WHERE property_id=%s AND tenant_id={_TENANT}
      AND (%s::timestamptz IS NULL OR (created_at,id)<(%s::timestamptz,%s::uuid))
      ORDER BY created_at DESC, id DESC LIMIT %s""", (property_id, at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'created_at')


@app.post('/v1/properties/{property_id}/requests/{request_id}/notes', status_code=201, response_model=NoteRecord)
def add_note(property_id: UUID, request_id: UUID, payload: NoteCreate, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, _role = access
    parent = readable_property(conn, property_id)
    try:
        row = conn.execute("""INSERT INTO diligence_notes(tenant_id,property_id,request_id,body)
          VALUES(%s,%s,%s,%s) RETURNING *""", (parent['tenant_id'], property_id, request_id, payload.body)).fetchone()
    except (psycopg.errors.InsufficientPrivilege, psycopg.errors.ForeignKeyViolation):
        raise HTTPException(404, 'Property not found') from None
    audit_diligence(conn, parent['tenant_id'], property_id, 'diligence.noted')
    return row


@app.get('/v1/properties/{property_id}/requests/{request_id}/notes', response_model=NotePage)
def list_notes(property_id: UUID, request_id: UUID, access=Depends(authorized_db, scope='function'), limit: int = Query(25, ge=1, le=100),
               cursor: str | None = Query(None, max_length=512)):
    conn, _role = access
    readable_property(conn, property_id)
    scope, at, record_id = cursor_context(conn, 'notes', cursor, request_id)
    rows = conn.execute(f"""SELECT * FROM diligence_notes WHERE property_id=%s AND request_id=%s AND tenant_id={_TENANT}
      AND (%s::timestamptz IS NULL OR (created_at,id)<(%s::timestamptz,%s::uuid))
      ORDER BY created_at DESC, id DESC LIMIT %s""", (property_id, request_id, at, at, record_id, limit + 1)).fetchall()
    return page_result(rows, limit, scope, 'created_at')


@app.post('/v1/properties/{property_id}/requests/{request_id}/close', response_model=RequestRecord)
def close_request(property_id: UUID, request_id: UUID, access=Depends(authorized_db, scope='function'), mfa=Depends(require_mfa)):
    conn, _role = access
    parent = writable_property(conn, property_id)
    row = conn.execute("""UPDATE diligence_requests SET status='closed', closed_at=clock_timestamp()
      WHERE id=%s AND property_id=%s AND status='open' RETURNING *""", (request_id, property_id)).fetchone()
    if row is None:
        raise HTTPException(404, 'Property not found')
    audit_diligence(conn, parent['tenant_id'], property_id, 'diligence.closed')
    return row
