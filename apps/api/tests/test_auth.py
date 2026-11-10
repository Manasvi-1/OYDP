import json
from datetime import datetime, timezone
from pathlib import Path
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


def test_localhost_http_issuer_requires_dev_flag(signing, monkeypatch):
    monkeypatch.delenv('OYDP_OIDC_DEV_HTTP', raising=False)
    monkeypatch.setenv('OIDC_ISSUER', 'http://127.0.0.1:8080/realms/oydp')
    monkeypatch.setenv('OIDC_JWKS_URL', 'http://127.0.0.1:8080/realms/oydp/protocol/openid-connect/certs')
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer '+signing[0]())
    assert exc.value.status_code == 503


def test_localhost_http_issuer_is_allowed_with_dev_flag(signing, monkeypatch):
    monkeypatch.setenv('OYDP_OIDC_DEV_HTTP', '1')
    monkeypatch.setenv('OIDC_ISSUER', 'http://127.0.0.1:8080/realms/oydp')
    monkeypatch.setenv('OIDC_JWKS_URL', 'http://127.0.0.1:8080/realms/oydp/protocol/openid-connect/certs')
    token, key, _ = signing
    claims = jwt.decode(token(), options={'verify_signature': False})
    claims['iss'] = 'http://127.0.0.1:8080/realms/oydp'
    local = jwt.encode(claims, key, algorithm='RS256', headers={'kid': 'test', 'typ': 'at+jwt'})
    assert verified_subject('Bearer '+local) == 'alice'


def test_non_loopback_http_denied_even_with_dev_flag(signing, monkeypatch):
    monkeypatch.setenv('OYDP_OIDC_DEV_HTTP', '1')
    monkeypatch.setenv('OIDC_ISSUER', 'http://identity.example.test')
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


def test_mfa_access_token(signing):
    from app.auth import require_mfa
    now = int(datetime.now(timezone.utc).timestamp())
    assert require_mfa('Bearer '+signing[0](amr=['pwd','mfa'], auth_time=now)) is True
    assert require_mfa('Bearer '+signing[0](amr=['pwd','otp'], auth_time=now)) is True


@pytest.mark.parametrize('amr', [[], ['pwd']])
def test_no_mfa_denied(signing, amr):
    from app.auth import require_mfa
    now = int(datetime.now(timezone.utc).timestamp())
    with pytest.raises(HTTPException) as exc:
        require_mfa('Bearer '+signing[0](amr=amr, auth_time=now))
    assert exc.value.status_code == 403


@pytest.mark.parametrize('amr', ['mfa', [1], None])
def test_malformed_mfa_claim_denied(signing, amr):
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer '+signing[0](amr=amr))
    assert exc.value.status_code == 401


def test_mfa_without_auth_time_is_not_fresh(signing):
    from app.auth import require_mfa
    with pytest.raises(HTTPException) as exc:
        require_mfa('Bearer '+signing[0](amr=['pwd', 'otp']))
    assert exc.value.status_code == 403
    assert exc.value.detail == 'Fresh MFA authentication required'


def test_stale_auth_time_denied(signing, monkeypatch):
    from app.auth import require_mfa
    monkeypatch.setenv('OYDP_MFA_MAX_AGE_SECONDS', '60')
    now = int(datetime.now(timezone.utc).timestamp())
    with pytest.raises(HTTPException) as exc:
        require_mfa('Bearer '+signing[0](amr=['pwd', 'otp'], auth_time=now - 61))
    assert exc.value.status_code == 403
    assert require_mfa('Bearer '+signing[0](amr=['pwd', 'otp'], auth_time=now - 30)) is True


def test_future_auth_time_denied(signing):
    from app.auth import require_mfa
    now = int(datetime.now(timezone.utc).timestamp())
    with pytest.raises(HTTPException) as exc:
        require_mfa('Bearer '+signing[0](amr=['pwd', 'otp'], auth_time=now + 120))
    assert exc.value.status_code == 403


@pytest.mark.parametrize('auth_time', [True, '1700000000', 1.5, -1])
def test_malformed_auth_time_denied(signing, auth_time):
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer '+signing[0](auth_time=auth_time))
    assert exc.value.status_code == 401


def test_mfa_freshness_can_be_disabled_explicitly(signing, monkeypatch):
    from app.auth import require_mfa
    monkeypatch.setenv('OYDP_MFA_MAX_AGE_SECONDS', '0')
    assert require_mfa('Bearer '+signing[0](amr=['pwd', 'mfa'])) is True


def test_invalid_mfa_max_age_fails_closed(signing, monkeypatch):
    from app.auth import require_mfa
    monkeypatch.setenv('OYDP_MFA_MAX_AGE_SECONDS', 'not-a-number')
    now = int(datetime.now(timezone.utc).timestamp())
    with pytest.raises(HTTPException) as exc:
        require_mfa('Bearer '+signing[0](amr=['pwd', 'otp'], auth_time=now))
    assert exc.value.status_code == 503


def test_optional_acr_allowlist(signing, monkeypatch):
    from app.auth import require_mfa
    monkeypatch.setenv('OYDP_MFA_ACR_VALUES', 'gold,silver')
    now = int(datetime.now(timezone.utc).timestamp())
    assert require_mfa('Bearer '+signing[0](amr=['pwd', 'otp'], auth_time=now, acr='gold')) is True
    with pytest.raises(HTTPException) as exc:
        require_mfa('Bearer '+signing[0](amr=['pwd', 'otp'], auth_time=now, acr='bronze'))
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        require_mfa('Bearer '+signing[0](amr=['pwd', 'otp'], auth_time=now))
    assert exc.value.status_code == 403


def test_expired_token_denied(signing):
    from app.auth import require_mfa
    now = int(datetime.now(timezone.utc).timestamp())
    token = 'Bearer '+signing[0](exp=1, amr=['pwd', 'otp'], auth_time=now)
    with pytest.raises(HTTPException) as exc:
        verified_subject(token)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        require_mfa(token)
    assert exc.value.status_code == 401


@pytest.mark.parametrize('audience', ['oydp-web', ['oydp-web', 'account']])
def test_wrong_audience_denied(signing, audience):
    from app.auth import require_mfa
    now = int(datetime.now(timezone.utc).timestamp())
    token = 'Bearer '+signing[0](aud=audience, amr=['pwd', 'otp'], auth_time=now)
    with pytest.raises(HTTPException) as exc:
        verified_subject(token)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        require_mfa(token)
    assert exc.value.status_code == 401


def test_non_mfa_token_denied_for_writes(signing):
    from app.auth import require_mfa
    now = int(datetime.now(timezone.utc).timestamp())
    token = 'Bearer '+signing[0](amr=['pwd'], auth_time=now)
    assert verified_subject(token) == 'alice'
    with pytest.raises(HTTPException) as exc:
        require_mfa(token)
    assert exc.value.status_code == 403


def test_missing_oidc_configuration_fails_closed(monkeypatch):
    for name in ('OIDC_ISSUER', 'OIDC_AUDIENCE', 'OIDC_JWKS_URL'):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(HTTPException) as exc:
        verified_subject('Bearer present')
    assert exc.value.status_code == 503


def test_local_realm_has_no_bypass_and_no_stored_users():
    realm_path = Path(__file__).resolve().parents[3] / 'infra' / 'keycloak' / 'oydp-realm.json'
    realm = json.loads(realm_path.read_text(encoding='utf-8'))
    assert realm['realm'] == 'oydp'
    assert realm['enabled'] is True
    assert realm['sslRequired'] == 'none'
    assert realm['registrationAllowed'] is False
    assert realm['browserFlow'] == 'oydp browser'
    assert 'users' not in realm
    assert 'credentials' not in json.dumps(realm)
    web = next(client for client in realm['clients'] if client['clientId'] == 'oydp-web')
    api = next(client for client in realm['clients'] if client['clientId'] == 'oydp-api')
    assert web['publicClient'] is True
    assert web['standardFlowEnabled'] is True
    assert web['implicitFlowEnabled'] is False
    assert web['directAccessGrantsEnabled'] is False
    assert web['serviceAccountsEnabled'] is False
    assert api['bearerOnly'] is True
    assert api['directAccessGrantsEnabled'] is False
    assert api['standardFlowEnabled'] is False
    assert web['attributes']['pkce.code.challenge.method'] == 'S256'
    assert web['attributes']['access.token.header.type.rfc9068'] == 'true'
    mappers = {item['name']: item for item in web['protocolMappers']}
    audience = mappers['api-audience']['config']
    assert audience['included.client.audience'] == 'oydp-api'
    assert audience['access.token.claim'] == 'true'
    assert audience['id.token.claim'] == 'false'
    amr = mappers['amr']['config']
    assert amr['access.token.claim'] == 'true'
    assert amr['id.token.claim'] == 'false'
    auth_time = mappers['auth-time']
    assert auth_time['protocolMapper'] == 'oidc-usersessionmodel-note-mapper'
    assert auth_time['config']['user.session.note'] == 'AUTH_TIME'
    assert auth_time['config']['claim.name'] == 'auth_time'
    assert auth_time['config']['jsonType.label'] == 'int'
    assert auth_time['config']['access.token.claim'] == 'true'
    flow = next(item for item in realm['authenticationFlows'] if item['alias'] == 'oydp browser')
    executions = {item['authenticator']: item for item in flow['authenticationExecutions']}
    assert set(executions) == {'auth-username-password-form', 'auth-otp-form'}
    assert all(item['requirement'] == 'REQUIRED' for item in executions.values())
    configs = {item['alias']: item['config'] for item in realm['authenticatorConfig']}
    assert configs[executions['auth-username-password-form']['authenticatorConfig']]['default.reference.value'] == 'pwd'
    otp = configs[executions['auth-otp-form']['authenticatorConfig']]
    assert otp['default.reference.value'] == 'otp'
    assert 1 <= int(otp['default.reference.maxAge']) <= 900
