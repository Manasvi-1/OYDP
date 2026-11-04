"""Synchronous content gate and encryption for private property documents.

This is not a malware sandbox or an antivirus product. It allows PDF, PNG, and
JPEG by magic bytes, rejects a few known active-content markers and the EICAR
test string, then encrypts accepted bytes. Production scanning remains an
owner decision.
"""
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_BYTES = 10 * 1024 * 1024
EICAR = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
PDF_MARKERS = (b'/JavaScript', b'/JS', b'/OpenAction', b'/Launch', b'/EmbeddedFile')


def encryption_key():
    raw = os.getenv('DOCUMENT_ENCRYPTION_KEY', '')
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        return None
    return key if len(key) == 32 else None


def storage_root():
    value = os.getenv('DOCUMENT_STORAGE_DIR', '')
    if not value:
        return None
    root = Path(value).resolve()
    if not root.is_dir():
        return None
    return root


def object_path(root, tenant_id, document_id):
    path = (root / str(tenant_id) / f'{document_id}.bin').resolve()
    if path.parent.parent != root or path.suffix != '.bin':
        raise ValueError('Document path escaped storage')
    return path


def inspect_bytes(data, limit=MAX_BYTES):
    if not data:
        return None, 'empty'
    if len(data) > limit:
        return None, 'size'
    if EICAR in data:
        return None, 'active'
    if data.startswith(b'%PDF-'):
        if any(marker in data for marker in PDF_MARKERS):
            return None, 'active'
        return 'application/pdf', None
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png', None
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg', None
    return None, 'type'


def seal_bytes(data, key):
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return nonce, ciphertext, hashlib.sha256(data).digest()


def open_bytes(nonce, ciphertext, key, expected_digest):
    try:
        data = AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception:
        return None
    if hashlib.sha256(data).digest() != bytes(expected_digest):
        return None
    return data
