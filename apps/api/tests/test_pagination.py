import base64
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.pagination import page_scope, encode_cursor, decode_cursor, page_result


def test_cursor_round_trip():
    scope=page_scope('claims','tenant','subject',uuid4())
    at=datetime.now(timezone.utc); record=uuid4()
    value=decode_cursor(encode_cursor(scope,at,record),scope)
    assert value.at==at and value.id==record
    assert decode_cursor(None,scope) is None


@pytest.mark.parametrize('token',['','not a cursor','%%%','e30','a'*513,'AAAA='])
def test_malformed_cursor_fails_closed(token):
    with pytest.raises(HTTPException) as exc:
        decode_cursor(token,'scope')
    assert exc.value.status_code==422
    assert exc.value.detail=='Invalid pagination cursor'


@pytest.mark.parametrize('value',[
    b'{"v":2,"scope":"scope","at":"2026-01-01T00:00:00Z","id":"00000000-0000-0000-0000-000000000001"}',
    b'{"v":1,"scope":"scope","at":"2026-01-01T00:00:00","id":"00000000-0000-0000-0000-000000000001"}',
    b'{"v":1,"scope":"scope","at":"2026-01-01T00:00:00Z","id":"bad"}',
])
def test_invalid_cursor_schema(value):
    token=base64.urlsafe_b64encode(value).decode().rstrip('=')
    with pytest.raises(HTTPException): decode_cursor(token,'scope')


def test_cursor_scope_is_not_reusable_for_other_context():
    at=datetime.now(timezone.utc)
    token=encode_cursor(page_scope('properties','t','alice'),at,uuid4())
    for scope in [page_scope('properties','t','bob'),page_scope('properties','other','alice'),page_scope('claims','t','alice',uuid4())]:
        with pytest.raises(HTTPException): decode_cursor(token,scope)
    assert page_scope('a|b','c','d')!=page_scope('a','b|c','d')


def test_page_uses_last_returned_row_and_has_no_total_count():
    at=datetime.now(timezone.utc);rows=[{'id':uuid4(),'created_at':at} for _ in range(3)]
    result=page_result(rows,2,'scope','created_at')
    assert result['items']==rows[:2]
    assert decode_cursor(result['next_cursor'],'scope').id==rows[1]['id']
    assert page_result([],2,'scope','created_at')=={'items':[],'next_cursor':None}
    assert page_result(rows[:2],2,'scope','created_at')['next_cursor'] is None
