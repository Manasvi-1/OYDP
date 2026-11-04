import base64
import hashlib
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPDefaultErrorHandler, HTTPErrorProcessor, HTTPHandler, OpenerDirector, Request

import jwt
import pytest

from app.auth import jwks_client, require_mfa, verified_subject
from tools.dev_oidc import DevOidc, from_env


@pytest.fixture
def issuer():
    server = DevOidc(
        'http://127.0.0.1:9', 'oydp-api', 'oydp-web', ['http://127.0.0.1:3000/auth/callback'], port=0)
    # port 0 selects a free port; the token issuer is rewritten to that port.
    server.port = 0
    server.start()
    server.issuer = f'http://127.0.0.1:{server.httpd.server_address[1]}'
    try:
        yield server
    finally:
        server.stop()


def _opener():
    director = OpenerDirector()
    director.add_handler(HTTPHandler())
    director.add_handler(HTTPDefaultErrorHandler())
    director.add_handler(HTTPErrorProcessor())
    return director


def _open(url, body=None):
    opener = _opener()
    request = Request(url, data=None if body is None else body.encode(), method='GET' if body is None else 'POST')
    if body is not None:
        request.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with opener.open(request, timeout=3) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def _get(url):
    return _open(url)


def _post(url, body):
    return _open(url, body)


def _pkce():
    verifier = 'a' * 48
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return verifier, challenge


def _login(server, subject='alice', mfa=True, verifier=None, challenge=None):
    verifier, generated = _pkce()
    challenge = challenge or generated
    query = (
        f'/authorize?response_type=code&client_id=oydp-web&redirect_uri=http://127.0.0.1:3000/auth/callback'
        f'&code_challenge={challenge}&code_challenge_method=S256&state=state-value-123456&resource=oydp-api'
    )
    status, _, page = _get(server.issuer + query)
    assert status == 200
    assert b'Development sign-in' in page
    form = 'state=state-value-123456&subject=' + subject + ('&mfa=1' if mfa else '')
    status, headers, body = _post(server.issuer + '/authorize', form)
    assert status == 302, body
    location = next(value for key, value in headers.items() if key.lower() == 'location')
    parsed = urlsplit(location)
    values = parse_qs(parsed.query)
    return verifier, values['code'][0], values['state'][0]


def _token(server, code, verifier, redirect='http://127.0.0.1:3000/auth/callback'):
    body = (
        'grant_type=authorization_code&client_id=oydp-web&code=' + code
        + '&redirect_uri=' + redirect + '&code_verifier=' + verifier
    )
    status, _, payload = _post(server.issuer + '/token', body)
    return status, payload


def _accept(monkeypatch, server, token):
    monkeypatch.setenv('OYDP_OIDC_DEV_HTTP', '1')
    monkeypatch.setenv('OIDC_ISSUER', server.issuer)
    monkeypatch.setenv('OIDC_AUDIENCE', 'oydp-api')
    monkeypatch.setenv('OIDC_JWKS_URL', server.issuer + '/.well-known/jwks.json')
    jwks_client.cache_clear()


def test_code_flow_matches_api_access_token_profile(issuer, monkeypatch):
    verifier, code, state = _login(issuer)
    assert state == 'state-value-123456'
    status, payload = _token(issuer, code, verifier)
    assert status == 200
    token = json.loads(payload)['access_token']
    header = jwt.get_unverified_header(token)
    assert header['alg'] == 'RS256' and header['typ'] == 'at+jwt' and header['kid'] == 'dev-1'
    claims = jwt.decode(token, issuer.key.public_key(), algorithms=['RS256'], audience='oydp-api', issuer=issuer.issuer)
    assert claims['sub'] == 'alice' and 'mfa' in claims['amr']
    _accept(monkeypatch, issuer, token)
    assert verified_subject('Bearer ' + token) == 'alice'
    jwks_client.cache_clear()


def test_unchecked_box_omits_mfa_and_api_denies_sensitive_routes(issuer, monkeypatch):
    verifier, code, _ = _login(issuer, mfa=False)
    status, payload = _token(issuer, code, verifier)
    assert status == 200
    token = json.loads(payload)['access_token']
    claims = jwt.decode(token, issuer.key.public_key(), algorithms=['RS256'], audience='oydp-api', issuer=issuer.issuer)
    assert claims['amr'] == ['pwd']
    _accept(monkeypatch, issuer, token)
    assert verified_subject('Bearer ' + token) == 'alice'
    with pytest.raises(Exception) as exc:
        require_mfa('Bearer ' + token)
    assert exc.value.status_code == 403
    jwks_client.cache_clear()


def test_code_is_single_use_and_pkce_bound(issuer):
    verifier, code, _ = _login(issuer, mfa=False)
    assert _token(issuer, code, 'b' * 48)[0] == 400
    # The failed exchange consumed the code. A correct retry must not succeed.
    assert _token(issuer, code, verifier)[0] == 400


def test_wrong_redirect_and_client_are_rejected(issuer):
    verifier, code, _ = _login(issuer)
    assert _token(issuer, code, verifier, redirect='http://127.0.0.1:3000/stolen')[0] == 400
    status, _, page = _get(issuer.issuer + '/authorize?response_type=token&client_id=other&redirect_uri=https://evil.test')
    assert status == 400
    assert b'access_token' not in page


def test_login_error_escapes_markup(issuer):
    status, _, body = _post(issuer.issuer + '/authorize', 'state=%22%3E%3Cscript%3E&subject=alice')
    assert status == 400
    assert b'<script>' not in body
    assert b'&lt;script&gt;' in body or b'&#34;&gt;&lt;script&gt;' in body or b'&#x27;' in body or b'&quot;&gt;&lt;script&gt;' in body


def test_implicit_flow_rejected(issuer):
    status, _, body = _get(issuer.issuer + '/authorize?response_type=token&client_id=oydp-web&redirect_uri=http://127.0.0.1:3000/auth/callback&code_challenge=' + _pkce()[1] + '&code_challenge_method=S256&state=state-value-123456')
    assert status == 400
    assert b'access_token' not in body


def test_refuses_unflagged_process_start(monkeypatch):
    monkeypatch.delenv('OYDP_DEV_OIDC', raising=False)
    with pytest.raises(SystemExit):
        from_env()


def test_non_loopback_issuer_rejected():
    with pytest.raises(ValueError):
        DevOidc('https://identity.example.test', 'oydp-api', 'oydp-web', [], host='127.0.0.1', port=9)
    with pytest.raises(ValueError):
        DevOidc('http://127.0.0.1:9', 'oydp-api', 'oydp-web', [], host='0.0.0.0', port=9)


def test_login_policy_names_the_issuer_and_redirect_origin(issuer):
    status, headers, _ = _get(issuer.issuer + '/authorize?response_type=code&client_id=oydp-web&redirect_uri=http://127.0.0.1:3000/auth/callback&code_challenge=' + _pkce()[1] + '&code_challenge_method=S256&state=state-value-123456')
    assert status == 200
    policy = next(value for key, value in headers.items() if key.lower() == 'content-security-policy')
    assert issuer.issuer in policy
    assert 'http://127.0.0.1:3000' in policy
    assert "form-action 'self'" not in policy


def test_discovery_stays_on_issuer_origin(issuer):
    status, _, body = _get(issuer.issuer + '/.well-known/openid-configuration')
    assert status == 200
    document = json.loads(body)
    assert document['issuer'] == issuer.issuer
    assert document['jwks_uri'].startswith(issuer.issuer)
    assert 'S256' in document['code_challenge_methods_supported']
