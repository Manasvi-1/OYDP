"""Document gate decisions. Payloads are generated in memory; none are customer files."""
import asyncio
from base64 import urlsafe_b64encode

import pytest
from fastapi.testclient import TestClient

from app.documents import (
    MAX_UPLOAD_BYTES, DocumentRejected, ScannerUnavailable, StorageUnavailable,
    aad_for, authenticated_plaintext, digest_bytes, gate_download, get_document_scanner,
    inspect_upload, read_declared_type, read_limited, reject_declared_length, scan_outcome,
    seal, storage_key, unseal,
)
from app.main import app

PDF = b'%PDF-1.4\n%OYDP-SYNTHETIC-CLEAN\n'
PNG = b'\x89PNG\r\n\x1a\nOYDP-SYNTHETIC-CLEAN'
JPEG = b'\xff\xd8\xffOYDP-SYNTHETIC-CLEAN\xff\xd9'


class _Chunks:
    def __init__(self, chunks):
        self.chunks = chunks

    async def stream(self):
        for chunk in self.chunks:
            yield chunk


class _Boom:
    def scan(self, payload, media_type):
        raise RuntimeError('scanner exploded')


class _Answer:
    def __init__(self, result):
        self.result = result

    def scan(self, payload, media_type):
        return self.result


def test_oversize_file_is_rejected():
    payload = b'%PDF-' + b'a' * MAX_UPLOAD_BYTES
    with pytest.raises(DocumentRejected) as exc:
        inspect_upload('application/pdf', payload)
    assert exc.value.status_code == 413
    assert exc.value.detail == 'Document exceeds the size limit'
    assert inspect_upload('application/pdf', b'%PDF-' + b'a' * (MAX_UPLOAD_BYTES - 5)) == 'application/pdf'


def test_declared_length_over_the_cap_is_rejected():
    reject_declared_length(str(MAX_UPLOAD_BYTES))
    with pytest.raises(DocumentRejected) as exc:
        reject_declared_length(str(MAX_UPLOAD_BYTES + 1))
    assert exc.value.status_code == 413
    with pytest.raises(DocumentRejected):
        reject_declared_length('nope')


def test_read_limited_does_not_keep_the_excess():
    request = _Chunks([b'%PDF-', b'a' * MAX_UPLOAD_BYTES])
    with pytest.raises(DocumentRejected) as exc:
        asyncio.run(read_limited(request))
    assert exc.value.status_code == 413
    assert asyncio.run(read_limited(_Chunks([PDF]))) == PDF


@pytest.mark.parametrize('declared,payload', [
    ('application/pdf', PNG),
    ('application/pdf', JPEG),
    ('image/png', PDF),
    ('image/jpeg', PDF),
    ('application/pdf', b'\x7fELF' + PDF),
    ('application/pdf', b'MZ' + PDF),
    ('application/pdf', b'<html>' + PDF),
])
def test_mismatched_content_is_rejected(declared, payload):
    with pytest.raises(DocumentRejected) as exc:
        inspect_upload(declared, payload)
    assert exc.value.status_code == 422
    assert exc.value.detail == 'Document content does not match the declared type'


def test_empty_document_is_rejected():
    with pytest.raises(DocumentRejected) as exc:
        inspect_upload('application/pdf', b'')
    assert exc.value.status_code == 422
    assert exc.value.detail == 'Document is empty'


@pytest.mark.parametrize('header', [
    None, '', 'text/plain', 'application/octet-stream', 'image/svg+xml',
    'application/pdf; charset=binary', 'application/pdf, image/png',
])
def test_disallowed_types_are_rejected(header):
    with pytest.raises(DocumentRejected) as exc:
        read_declared_type(header)
    assert exc.value.status_code in (415, 422)


@pytest.mark.parametrize('header,media', [
    ('application/pdf', 'application/pdf'),
    ('APPLICATION/PDF', 'application/pdf'),
    (' image/png ', 'image/png'),
    ('image/jpeg', 'image/jpeg'),
])
def test_allowlisted_types_match_magic(header, media):
    body = {'application/pdf': PDF, 'image/png': PNG, 'image/jpeg': JPEG}[media]
    assert inspect_upload(header, body) == media


@pytest.mark.parametrize('state', ['quarantined', 'fail', 'scanner_unavailable', 'pass ', 'PASS', ''])
def test_download_denied_until_clean_scan(state):
    with pytest.raises(DocumentRejected) as exc:
        gate_download(state)
    assert exc.value.status_code == 403
    gate_download('pass')


def test_absent_scanner_fails_closed():
    assert get_document_scanner() is None
    with pytest.raises(ScannerUnavailable):
        scan_outcome(None, PDF, 'application/pdf')
    with pytest.raises(ScannerUnavailable):
        scan_outcome(_Boom(), PDF, 'application/pdf')
    for answer in ('PASS', 'clean', 'ok', '', None, True):
        with pytest.raises(ScannerUnavailable):
            scan_outcome(_Answer(answer), PDF, 'application/pdf')
    assert scan_outcome(_Answer('fail'), PDF, 'application/pdf') == 'fail'
    assert scan_outcome(_Answer('pass'), PDF, 'application/pdf') == 'pass'


def test_ciphertext_roundtrip_and_wrong_key_fail_closed(monkeypatch):
    key = b'A' * 32
    aad = aad_for('tenant', 'property', 'document', 'application/pdf')
    nonce, ciphertext = seal(key, PDF, aad)
    assert ciphertext != PDF
    assert PDF not in ciphertext
    assert unseal(key, nonce, ciphertext, aad) == PDF
    with pytest.raises(StorageUnavailable):
        unseal(b'B' * 32, nonce, ciphertext, aad)
    with pytest.raises(StorageUnavailable):
        unseal(key, nonce, ciphertext, aad + b'x')
    monkeypatch.delenv('DOCUMENT_STORAGE_KEY', raising=False)
    with pytest.raises(StorageUnavailable):
        storage_key()
    monkeypatch.setenv('DOCUMENT_STORAGE_KEY', urlsafe_b64encode(b'short').decode())
    with pytest.raises(StorageUnavailable):
        storage_key()
    monkeypatch.setenv('DOCUMENT_STORAGE_KEY', urlsafe_b64encode(key).decode())
    opened = authenticated_plaintext(storage_key(), nonce, ciphertext, aad, 'application/pdf', len(PDF), digest_bytes(PDF))
    assert opened == PDF


def test_routes_fail_closed_without_authentication():
    client = TestClient(app)
    property_id = '00000000-0000-0000-0000-000000000001'
    document_id = '00000000-0000-0000-0000-000000000002'
    headers = {'X-Tenant-ID': '00000000-0000-0000-0000-000000000003', 'Content-Type': 'application/pdf'}
    assert client.post(f'/v1/properties/{property_id}/documents', headers=headers, content=PDF).status_code == 503
    assert client.post(f'/v1/properties/{property_id}/documents/{document_id}/scan', headers=headers).status_code == 503
    denied = client.get(f'/v1/properties/{property_id}/documents/{document_id}/content', headers=headers)
    assert denied.status_code == 503
    assert PDF not in denied.content


def test_routes_reject_a_malformed_token(monkeypatch):
    monkeypatch.setenv('OIDC_ISSUER', 'https://identity.example.test')
    monkeypatch.setenv('OIDC_AUDIENCE', 'oydp-api')
    monkeypatch.setenv('OIDC_JWKS_URL', 'https://identity.example.test/keys')
    client = TestClient(app)
    headers = {
        'Authorization': 'Bearer not-a-token',
        'X-Tenant-ID': '00000000-0000-0000-0000-000000000003',
        'Content-Type': 'application/pdf',
    }
    property_id = '00000000-0000-0000-0000-000000000001'
    document_id = '00000000-0000-0000-0000-000000000002'
    assert client.post(f'/v1/properties/{property_id}/documents', headers=headers, content=PDF).status_code == 401
    assert client.get(f'/v1/properties/{property_id}/documents/{document_id}/content', headers=headers).status_code == 401
