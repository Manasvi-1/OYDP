import hashlib
from pathlib import Path

import pytest

from app.documents import inspect_bytes, object_path, open_bytes, seal_bytes

PNG = b'\x89PNG\r\n\x1a\n' + b'png-body'
JPEG = b'\xff\xd8\xff' + b'jpeg-body'
PDF = b'%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF'
ACTIVE = b'%PDF-1.4\n/JavaScript (alert)\n%%EOF'
EICAR = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'


def test_content_gate_allows_plain_documents_and_rejects_active_content():
    assert inspect_bytes(PNG) == ('image/png', None)
    assert inspect_bytes(JPEG) == ('image/jpeg', None)
    assert inspect_bytes(PDF) == ('application/pdf', None)
    assert inspect_bytes(ACTIVE)[1] == 'active'
    assert inspect_bytes(b'<html></html>')[1] == 'type'
    assert inspect_bytes(EICAR)[1] == 'active'
    assert inspect_bytes(b'')[1] == 'empty'
    assert inspect_bytes(b'x' * 11, limit=10)[1] == 'size'


def test_seal_round_trip_and_digest_mismatch(tmp_path):
    key = hashlib.sha256(b'test-key').digest()
    nonce, ciphertext, digest = seal_bytes(PNG, key)
    assert ciphertext != PNG
    assert open_bytes(nonce, ciphertext, key, digest) == PNG
    assert open_bytes(nonce, ciphertext, key, b'\x00' * 32) is None
    assert open_bytes(nonce, ciphertext, hashlib.sha256(b'other').digest(), digest) is None
    root = tmp_path
    path = object_path(root.resolve(), '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222')
    assert path.parent.parent == root.resolve()
    with pytest.raises(ValueError):
        object_path(root.resolve(), '..', '22222222-2222-4222-8222-222222222222')
    assert Path(path).name.endswith('.bin')
