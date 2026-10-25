from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from app.auth import verified_subject


@pytest.fixture
def signing(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv('OIDC_ISSUER', 'https://identity.example.test')
    monkeypatch.setenv('OIDC_AUDIENCE', 'oydp-api')
    monkeypatch.setenv('OIDC_JWKS_URL', 'https://identity.example.test/keys')
    client = Mock()
    client.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    monkeypatch.setattr('app.auth.jwks_client', lambda _: client)
    now = int(datetime.now(timezone.utc).timestamp())
    def token(**changes):
        claims = dict(iss='https://identity.example.test', aud='oydp-api', sub='alice', iat=now, exp=now+300)
        claims.update(changes)
        return jwt.encode(claims, key, algorithm='RS256', headers={'kid': 'test', 'typ': 'at+jwt'})
    return token, key, client


def test_verified_access_token(signing):
    assert verified_subject('Bearer '+signing[0]()) == 'alice'


@pytest.mark.parametrize('changes', [{'exp': 1}, {'aud': 'other'}, {'iss': 'https://evil.test'}, {'sub': ''}, {'sub': ' '*3}, {'sub': 'a'*256}, {'iat': 9999999999}, {'nbf': 9999999999}])
def test_invalid_claims(signing, changes):
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer '+signing[0](**changes))
    assert exc.value.status_code == 401


def test_forged_signature(signing):
    token, _, _ = signing
    claims = jwt.decode(token(), options={'verify_signature': False})
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(claims, attacker, algorithm='RS256', headers={'kid': 'test', 'typ': 'at+jwt'})
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer '+forged)
    assert exc.value.status_code == 401


@pytest.mark.parametrize('value', [None, '', 'Basic secret', 'Bearer broken', 'Bearer '+ 'x'*17000])
def test_bad_authorization(signing, value):
    with pytest.raises(HTTPException) as exc:
        verified_subject(value)
    assert exc.value.status_code == 401


@pytest.mark.parametrize('headers', [{'typ':'JWT', 'kid':'test'}, {'typ':'at+jwt'}, {'typ':'at+jwt','kid':'test','crit':['unknown']}])
def test_reject_id_tokens_and_unsupported_headers(signing, headers):
    token, key, client = signing
    claims = jwt.decode(token(), options={'verify_signature':False})
    value = jwt.encode(claims, key, algorithm='RS256', headers=headers)
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer '+value)
    assert exc.value.status_code == 401
    client.get_signing_key_from_jwt.assert_not_called()


def test_provider_failure(signing):
    signing[2].get_signing_key_from_jwt.side_effect = jwt.PyJWKClientConnectionError('offline')
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer '+signing[0]())
    assert exc.value.status_code == 503


def test_https_required(signing, monkeypatch):
    monkeypatch.setenv('OIDC_JWKS_URL', 'http://identity.example.test/keys')
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer '+signing[0]())
    assert exc.value.status_code == 503


def test_jwks_rotation(monkeypatch):
    import json
    from jwt.algorithms import RSAAlgorithm
    from app.auth import jwks_client
    jwks_client.cache_clear()
    keys = [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]
    jwks = []
    for index, key in enumerate(keys):
        jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
        jwk.update(kid=str(index), use='sig', alg='RS256')
        jwks.append(jwk)
    client = jwks_client('https://identity.example.test/keys')
    # Mock only the network; exercise PyJWKClient key selection and new-key refresh.
    monkeypatch.setattr(client, 'fetch_data', Mock(side_effect=[{'keys':[jwks[0]]}, {'keys':[jwks[1]]}]))
    for index, key in enumerate(keys):
        token = jwt.encode({'sub':'alice'}, key, algorithm='RS256', headers={'kid':str(index)})
        selected = client.get_signing_key_from_jwt(token)
        assert jwt.decode(token, selected.key, algorithms=['RS256'])['sub'] == 'alice'
    assert client.fetch_data.call_count == 2
    jwks_client.cache_clear()
