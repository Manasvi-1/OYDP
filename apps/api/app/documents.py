"""Untrusted-document gate. Bytes stay quarantined until a scanner marks them clean.

No scanner is included. An absent, failing, or unexpected scanner cannot release bytes.
This module does not parse PDF, image, or text structure and does not log payloads.
"""
import hashlib
import hmac
import os
import secrets
from base64 import urlsafe_b64decode

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_UPLOAD_BYTES = 1_048_576
_MAGIC = {
    'application/pdf': b'%PDF-',
    'image/png': b'\x89PNG\r\n\x1a\n',
    'image/jpeg': b'\xff\xd8\xff',
}


class DocumentRejected(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


class ScannerUnavailable(Exception):
    """The scanner is absent or did not return a usable decision."""


class StorageUnavailable(Exception):
    """The encryption key is missing or the ciphertext cannot be opened."""


def get_document_scanner():
    """Return a scanner adapter. None means the scanner is not installed."""
    return None


def read_declared_type(header: str | None) -> str:
    if header is None:
        raise DocumentRejected(422, 'Document type is not allowed')
    media = header.strip().lower()
    if not media or any(mark in media for mark in (';', ' ', ',', '\n', '\r', '\x00')):
        raise DocumentRejected(422, 'Document type is not allowed')
    if media not in _MAGIC:
        raise DocumentRejected(415, 'Document type is not allowed')
    return media


def inspect_upload(declared: str | None, payload: bytes) -> str:
    """Accept only a bounded allowlist whose bytes start with that type's magic."""
    media = read_declared_type(declared)
    if not isinstance(payload, (bytes, bytearray)):
        raise DocumentRejected(422, 'Document content does not match the declared type')
    payload = bytes(payload)
    if not payload:
        raise DocumentRejected(422, 'Document is empty')
    if len(payload) > MAX_UPLOAD_BYTES:
        raise DocumentRejected(413, 'Document exceeds the size limit')
    if not payload.startswith(_MAGIC[media]):
        raise DocumentRejected(422, 'Document content does not match the declared type')
    return media


def reject_declared_length(header: str | None, limit: int = MAX_UPLOAD_BYTES) -> None:
    if header is None:
        return
    try:
        size = int(header)
    except ValueError:
        raise DocumentRejected(422, 'Document exceeds the size limit')
    if size < 0 or size > limit:
        raise DocumentRejected(413, 'Document exceeds the size limit')


async def read_limited(request, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    """Stop once the body exceeds the cap. Excess bytes are not retained."""
    received = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        if len(received) + len(chunk) > limit:
            raise DocumentRejected(413, 'Document exceeds the size limit')
        received.extend(chunk)
    return bytes(received)


def gate_download(scan_state: str) -> None:
    """Only a clean scan may be released. Every other state stays closed."""
    if scan_state != 'pass':
        raise DocumentRejected(403, 'Document is not available')


def scan_outcome(scanner, payload: bytes, media_type: str) -> str:
    """Return pass or fail. Absence, errors, and unknown answers fail closed."""
    if scanner is None:
        raise ScannerUnavailable()
    try:
        result = scanner.scan(payload, media_type)
    except Exception:
        raise ScannerUnavailable() from None
    if result == 'pass':
        return 'pass'
    if result == 'fail':
        return 'fail'
    raise ScannerUnavailable()


def storage_key() -> bytes:
    raw = os.environ.get('DOCUMENT_STORAGE_KEY', '').strip()
    if not raw:
        raise StorageUnavailable()
    try:
        key = urlsafe_b64decode(raw)
    except Exception:
        raise StorageUnavailable() from None
    if len(key) != 32:
        raise StorageUnavailable()
    return key


def aad_for(tenant_id, property_id, document_id, media_type: str) -> bytes:
    return f'{tenant_id}|{property_id}|{document_id}|{media_type}'.encode('ascii')


def seal(key: bytes, plaintext: bytes, aad: bytes) -> tuple[bytes, bytes]:
    nonce = secrets.token_bytes(12)
    return nonce, AESGCM(key).encrypt(nonce, plaintext, aad)


def unseal(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    try:
        return AESGCM(key).decrypt(bytes(nonce), bytes(ciphertext), aad)
    except (InvalidTag, ValueError):
        raise StorageUnavailable() from None


def digest_bytes(payload: bytes) -> bytes:
    return hashlib.sha256(payload).digest()


def authenticated_plaintext(key, nonce, ciphertext, aad, media_type, expected_size, expected_digest) -> bytes:
    """Open ciphertext only after the caller has already authorized a clean scan."""
    plain = unseal(key, nonce, ciphertext, aad)
    if len(plain) != expected_size or len(plain) > MAX_UPLOAD_BYTES:
        raise StorageUnavailable()
    if not hmac.compare_digest(digest_bytes(plain), bytes(expected_digest)):
        raise StorageUnavailable()
    if inspect_upload(media_type, plain) != media_type:
        raise StorageUnavailable()
    return plain
