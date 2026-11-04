"""Verify access tokens using an operator-configured issuer and HTTPS JWKS."""
import os
from functools import lru_cache
from urllib.parse import urlsplit

import jwt
from fastapi import Header, HTTPException


@lru_cache(maxsize=8)
def jwks_client(url):
    return jwt.PyJWKClient(url, timeout=5, lifespan=300, cache_keys=False)


def verified_claims(authorization: str | None) -> dict:
    issuer = os.getenv('OIDC_ISSUER', '')
    audience = os.getenv('OIDC_AUDIENCE', '')
    url = os.getenv('OIDC_JWKS_URL', '')
    if not all((issuer, audience, url)):
        raise HTTPException(503, 'OIDC authentication not configured')
    for value in (issuer, url):
        parts = urlsplit(value)
        local = parts.scheme == 'http' and parts.hostname in {'localhost', '127.0.0.1'}
        if not (parts.scheme == 'https' or local) or not parts.hostname or parts.username or parts.password or parts.fragment:
            raise HTTPException(503, 'Invalid OIDC configuration')
    if not authorization or len(authorization) > 16384:
        raise HTTPException(401, 'Bearer access token required', headers={'WWW-Authenticate': 'Bearer'})
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token or ' ' in token:
        raise HTTPException(401, 'Bearer access token required', headers={'WWW-Authenticate': 'Bearer'})
    try:
        header = jwt.get_unverified_header(token)
        # Reject ID tokens and algorithm confusion before fetching keys. Never use jku/x5u.
        if header.get('alg') != 'RS256' or header.get('typ') != 'at+jwt' or not header.get('kid') or header.get('crit'):
            raise jwt.InvalidTokenError('Unsupported access token')
        key = jwks_client(url).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], issuer=issuer, audience=audience,
                            options={'require': ['iss', 'aud', 'sub', 'exp', 'iat']})
        subject = claims['sub']
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
            raise jwt.InvalidTokenError('Invalid subject')
        amr = claims.get('amr', [])
        if not isinstance(amr, list) or any(not isinstance(item, str) for item in amr):
            raise jwt.InvalidTokenError('Invalid authentication methods')
        return claims
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, 'Identity provider unavailable') from None
    except jwt.PyJWTError:
        raise HTTPException(401, 'Invalid access token', headers={'WWW-Authenticate': 'Bearer'}) from None


def verified_subject(authorization: str | None = Header(default=None)) -> str:
    return verified_claims(authorization)['sub']


def require_mfa(authorization: str | None = Header(default=None)) -> bool:
    # Keycloak records TOTP as otp. The synthetic test tokens use mfa.
    if not {'mfa', 'otp'}.intersection(verified_claims(authorization).get('amr', [])):
        raise HTTPException(403, 'MFA access token required')
    return True
