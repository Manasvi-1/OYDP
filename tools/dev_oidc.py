"""Loopback development OIDC issuer for the property API access-token profile.

This process mints RS256 ``typ=at+jwt`` access tokens so a browser can complete
authorization-code + PKCE against the same checks ``app.auth`` already enforces.
It does not enroll authenticators, prove identity, or choose a production
provider. It refuses to start unless ``OYDP_DEV_OIDC=1`` and it binds loopback
HTTP only.
"""
import base64
import hashlib
import html
import json
import os
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SUBJECT = re.compile(r'^[A-Za-z0-9._:-]{1,64}$')
CHALLENGE = re.compile(r'^[A-Za-z0-9_-]{43,128}$')


class DevOidc:
    def __init__(self, issuer, audience, client_id, redirects, host='127.0.0.1', port=None):
        parsed = urlsplit(issuer)
        if parsed.scheme != 'http' or (parsed.hostname or '').lower().rstrip('.') not in {'localhost', '127.0.0.1'}:
            raise ValueError('Development issuer must be loopback http')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Development issuer URL must not carry credentials or a query')
        if host not in {'127.0.0.1', 'localhost'}:
            raise ValueError('Development issuer must bind to loopback')
        self.issuer = issuer.rstrip('/')
        self.audience = audience
        self.client_id = client_id
        self.redirects = frozenset(redirects)
        self.host = host
        self.port = parsed.port if port is None else port
        if self.port is None:
            raise ValueError('Development issuer needs an explicit port')
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = 'dev-1'
        self._pending = {}
        self._codes = {}
        self._lock = threading.Lock()
        self.httpd = None
        self.thread = None

    def jwks(self):
        document = json.loads(RSAAlgorithm.to_jwk(self.key.public_key()))
        document.update(kid=self.kid, use='sig', alg='RS256')
        return {'keys': [document]}

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                owner.dispatch(self, 'GET')

            def do_POST(self):
                owner.dispatch(self, 'POST')

        class BoundServer(ThreadingHTTPServer):
            allow_reuse_address = True

        self.httpd = BoundServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    def dispatch(self, request, method):
        try:
            length = int(request.headers.get('Content-Length', '0') or 0)
        except ValueError:
            return self._send(request, 400, {'error': 'invalid_request'})
        if length < 0 or length > 8192:
            return self._send(request, 413, {'error': 'invalid_request'})
        raw = request.rfile.read(length) if length else b''
        parsed = urlsplit(request.path)
        form = parse_qs(raw.decode('utf-8', 'replace'), keep_blank_values=False, max_num_fields=20)
        query = parse_qs(parsed.query, keep_blank_values=False, max_num_fields=20)
        self._sweep()
        path = parsed.path
        if method == 'GET' and path == '/.well-known/openid-configuration':
            return self._send(request, 200, self.discovery())
        if method == 'GET' and path == '/.well-known/jwks.json':
            return self._send(request, 200, self.jwks())
        if method == 'GET' and path == '/authorize':
            return self.authorize(request, query)
        if method == 'POST' and path == '/authorize':
            return self.finish_login(request, form)
        if method == 'POST' and path == '/token':
            return self.token(request, form)
        return self._send(request, 404, {'error': 'not_found'})

    def form_policy(self):
        # Chromium does not treat form-action 'self' as the loopback origin, so name it.
        # The policy also has to allow the browser to follow the code redirect.
        origins = {self.issuer}
        for redirect in self.redirects:
            parts = urlsplit(redirect)
            if parts.scheme and parts.netloc:
                origins.add(f'{parts.scheme}://{parts.netloc}')
        return "default-src 'none'; form-action " + ' '.join(sorted(origins)) + "; base-uri 'none'; frame-ancestors 'none'"

    def discovery(self):
        return {
            'issuer': self.issuer,
            'authorization_endpoint': self.issuer + '/authorize',
            'token_endpoint': self.issuer + '/token',
            'jwks_uri': self.issuer + '/.well-known/jwks.json',
            'response_types_supported': ['code'],
            'subject_types_supported': ['public'],
            'id_token_signing_alg_values_supported': ['RS256'],
            'code_challenge_methods_supported': ['S256'],
            'grant_types_supported': ['authorization_code'],
        }

    def authorize(self, request, query):
        redirect = one(query, 'redirect_uri')
        challenge = one(query, 'code_challenge')
        resource = one(query, 'resource') or self.audience
        if (
            one(query, 'response_type') != 'code'
            or one(query, 'client_id') != self.client_id
            or one(query, 'code_challenge_method') != 'S256'
            or one(query, 'response_mode') not in (None, 'query')
            or redirect not in self.redirects
            or not challenge or not CHALLENGE.fullmatch(challenge)
            or resource != self.audience
        ):
            return self._send(request, 400, {'error': 'invalid_request'})
        state = one(query, 'state')
        if not state or len(state) < 16 or len(state) > 200:
            return self._send(request, 400, {'error': 'invalid_request'})
        with self._lock:
            self._pending[state] = {
                'redirect': redirect,
                'challenge': challenge,
                'nonce': one(query, 'nonce'),
                'exp': time.time() + 600,
            }
        return self._html(request, login_page(state))

    def finish_login(self, request, form):
        state = one(form, 'state')
        subject = one(form, 'subject') or ''
        with self._lock:
            pending = self._pending.pop(state, None)
        if not pending or pending['exp'] < time.time() or not SUBJECT.fullmatch(subject):
            return self._html(request, login_page(state or '', 'Use a short development subject and start sign-in again.'), 400)
        code = secrets.token_urlsafe(32)
        with self._lock:
            self._codes[code] = {
                'subject': subject,
                'mfa': one(form, 'mfa') == '1',
                'redirect': pending['redirect'],
                'challenge': pending['challenge'],
                'nonce': pending['nonce'],
                'exp': time.time() + 120,
            }
        location = pending['redirect'] + ('&' if '?' in pending['redirect'] else '?') + urlencode({'code': code, 'state': state})
        return self._send(request, 302, b'', 'text/plain', [('Location', location)])

    def token(self, request, form):
        code = one(form, 'code')
        with self._lock:
            saved = self._codes.pop(code, None) if code else None
        verifier = one(form, 'code_verifier') or ''
        digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        if (
            one(form, 'grant_type') != 'authorization_code'
            or one(form, 'client_id') != self.client_id
            or not saved
            or saved['exp'] < time.time()
            or one(form, 'redirect_uri') != saved['redirect']
            or not verifier
            or digest != saved['challenge']
        ):
            return self._send(request, 400, {'error': 'invalid_grant'})
        now = int(time.time())
        amr = ['pwd', 'mfa'] if saved['mfa'] else ['pwd']
        # auth_time is the synthetic login instant. The checkbox still is not a real authenticator.
        token = jwt.encode(
            {'iss': self.issuer, 'aud': self.audience, 'sub': saved['subject'], 'iat': now, 'exp': now + 600,
             'auth_time': now, 'amr': amr, 'nonce': saved['nonce']},
            self.key, algorithm='RS256', headers={'kid': self.kid, 'typ': 'at+jwt'})
        return self._send(request, 200, {'access_token': token, 'token_type': 'Bearer', 'expires_in': 600})

    def _sweep(self):
        now = time.time()
        with self._lock:
            self._pending = {k: v for k, v in self._pending.items() if v['exp'] >= now}
            self._codes = {k: v for k, v in self._codes.items() if v['exp'] >= now}

    def _html(self, request, body, status=200):
        return self._send(request, status, body.encode(), 'text/html; charset=utf-8')

    def _send(self, request, status, body, content_type='application/json', extra=()):
        if isinstance(body, dict):
            payload = json.dumps(body).encode()
        elif isinstance(body, bytes):
            payload = body
        else:
            payload = body.encode()
        request.send_response(status)
        request.send_header('Content-Type', content_type)
        request.send_header('Content-Length', str(len(payload)))
        request.send_header('Cache-Control', 'no-store')
        request.send_header('X-Content-Type-Options', 'nosniff')
        request.send_header('Referrer-Policy', 'no-referrer')
        request.send_header('Content-Security-Policy', self.form_policy())
        for name, value in extra:
            request.send_header(name, value)
        request.end_headers()
        request.wfile.write(payload)


def one(values, name):
    found = values.get(name) or []
    if len(found) != 1:
        return None
    return found[0]


def login_page(state, error=''):
    message = f'<p>{html.escape(error)}</p>' if error else ''
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>OYDP development sign-in</title></head>
<body>
<h1>Development sign-in</h1>
<p>This loopback issuer only creates access tokens for the property API. It does not prove identity, perform MFA, or grant a tenancy.</p>
{message}
<form method="post" action="/authorize">
<input type="hidden" name="state" value="{html.escape(state)}">
<label>Subject <input name="subject" autocomplete="off" required></label>
<label><input type="checkbox" name="mfa" value="1"> Set amr to include mfa. This is not an authenticator.</label>
<button type="submit">Continue</button>
</form>
</body></html>'''


def from_env():
    if os.getenv('OYDP_DEV_OIDC') != '1':
        raise SystemExit('Refusing to start: set OYDP_DEV_OIDC=1 for the loopback development issuer')
    redirects = [item for item in os.getenv('OYDP_DEV_OIDC_REDIRECTS', '').split(',') if item]
    return DevOidc(
        os.environ['OYDP_DEV_OIDC_ISSUER'],
        os.environ['OYDP_DEV_OIDC_AUDIENCE'],
        os.environ['OYDP_DEV_OIDC_CLIENT_ID'],
        redirects,
    )


if __name__ == '__main__':
    server = from_env()
    server.start()
    print(f'development oidc listening on {server.issuer}', flush=True)
    try:
        server.thread.join()
    except KeyboardInterrupt:
        server.stop()
