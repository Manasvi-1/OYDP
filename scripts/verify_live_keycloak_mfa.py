#!/usr/bin/env python3
"""Inspect a live local Keycloak access token without printing secrets.

Usage (after a real browser OIDC+MFA login against compose identity):
  set OYDP_LIVE_ACCESS_TOKEN_PATH to a file that contains only the access token
  (one line, no other secrets). This script prints sanitized claim evidence only.

Exit codes:
  0  claims match the OYDP MFA freshness contract
  2  Keycloak / token unavailable (BLOCKED)
  3  token present but claims fail the contract
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt


def _get(url: str, timeout: float = 5.0) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method='GET', headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except OSError as exc:
        raise SystemExit(f'BLOCKED: cannot reach identity provider ({exc})') from None


def _sanitize(claims: dict) -> dict:
    allowed = ('iss', 'aud', 'sub', 'iat', 'exp', 'auth_time', 'amr', 'acr', 'typ')
    out = {}
    for key in allowed:
        if key not in claims:
            continue
        value = claims[key]
        if key == 'sub' and isinstance(value, str):
            out[key] = f'<redacted len={len(value)}>'
        elif key == 'aud':
            out[key] = value
        else:
            out[key] = value
    out['has_auth_time'] = 'auth_time' in claims
    out['amr_has_mfa_or_otp'] = bool(set(claims.get('amr') or []) & {'mfa', 'otp'})
    if 'auth_time' in claims and isinstance(claims['auth_time'], int):
        out['auth_age_seconds'] = max(0, int(time.time()) - claims['auth_time'])
    return out


def main() -> int:
    issuer = os.getenv('OIDC_ISSUER', 'http://127.0.0.1:8080/realms/oydp').rstrip('/')
    audience = os.getenv('OIDC_AUDIENCE', 'oydp-api')
    jwks_url = os.getenv('OIDC_JWKS_URL', f'{issuer}/protocol/openid-connect/certs')
    openid = f'{issuer}/.well-known/openid-configuration'

    try:
        status, body = _get(openid)
    except SystemExit as exc:
        print(exc)
        return 2
    if status != 200:
        print(f'BLOCKED: OpenID discovery returned HTTP {status}')
        return 2
    discovery = json.loads(body.decode('utf-8'))
    if discovery.get('issuer', '').rstrip('/') != issuer:
        print('BLOCKED: discovery issuer mismatch')
        return 2
    print('Keycloak discovery: VERIFIED (issuer reachable)')

    token_path = os.getenv('OYDP_LIVE_ACCESS_TOKEN_PATH', '').strip()
    if not token_path:
        print('Live token claims: BLOCKED (set OYDP_LIVE_ACCESS_TOKEN_PATH after browser MFA login)')
        print('Required next steps: enroll disposable user per docs/implementation/IDENTITY_GATE.md,')
        print('complete password+OTP browser login, write the access token to a local file, re-run.')
        return 2

    path = Path(token_path)
    if not path.is_file():
        print('BLOCKED: OYDP_LIVE_ACCESS_TOKEN_PATH is not a readable file')
        return 2
    token = path.read_text(encoding='utf-8').strip()
    if not token or any(ch.isspace() for ch in token) or len(token) > 16384:
        print('BLOCKED: token file is empty or malformed')
        return 2

    try:
        header = jwt.get_unverified_header(token)
        if header.get('alg') != 'RS256' or header.get('typ') != 'at+jwt' or not header.get('kid'):
            print('FAIL: access token header is not RS256 at+jwt with kid')
            return 3
        key = jwt.PyJWKClient(jwks_url, timeout=5).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            issuer=issuer,
            audience=audience,
            options={'require': ['iss', 'aud', 'sub', 'exp', 'iat']},
        )
    except Exception as exc:  # noqa: BLE001 - report verification outcome only
        print(f'FAIL: access token verification failed ({type(exc).__name__})')
        return 3

    evidence = _sanitize(claims)
    print('Sanitized claim evidence:')
    print(json.dumps(evidence, sort_keys=True))
    failures = []
    if not evidence['amr_has_mfa_or_otp']:
        failures.append('amr missing mfa/otp')
    if not evidence['has_auth_time'] or type(claims.get('auth_time')) is not int:
        failures.append('auth_time missing or not int')
    elif claims['auth_time'] > int(time.time()):
        failures.append('auth_time in the future')
    if failures:
        print('FAIL: ' + '; '.join(failures))
        return 3
    print('Live access-token MFA claims: VERIFIED')
    print('Note: refresh/stale/password-only scenarios require separate timed browser runs.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
