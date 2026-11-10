"""Verify access tokens using an operator-configured issuer and HTTPS JWKS."""
import os
import time
from functools import lru_cache
from urllib.parse import urlsplit

import jwt
from fastapi import Header, HTTPException

# Default freshness window matches the local Keycloak AMR maxAge (900s).
# Presence of mfa/otp in amr alone is not treated as a fresh MFA step-up.
_DEFAULT_MFA_MAX_AGE_SECONDS = 900
_MFA_METHODS = frozenset({'mfa', 'otp'})


@lru_cache(maxsize=8)
def jwks_client(url):
    return jwt.PyJWKClient(url, timeout=5, lifespan=300, cache_keys=False)


def endpoint_allowed(value: str) -> bool:
    """HTTPS endpoints are the production rule. Plain HTTP is accepted only for an
    explicit loopback development issuer, so a local sign-in can mint the same
    access-token profile this module already verifies."""
    parts = urlsplit(value)
    if parts.username or parts.password or parts.fragment or parts.query or not parts.hostname:
        return False
    if parts.scheme == 'https':
        return True
    host = parts.hostname.lower().rstrip('.')
    return parts.scheme == 'http' and os.getenv('OYDP_OIDC_DEV_HTTP') == '1' and host in {'localhost', '127.0.0.1'}


def loopback_oidc_dev_enabled() -> bool:
    """True only when the operator explicitly allows loopback HTTP OIDC for local work."""
    return os.getenv('OYDP_OIDC_DEV_HTTP') == '1'


def mfa_max_age_seconds() -> int | None:
    """Return the MFA freshness window in seconds.

    Unset env uses the default window. Explicit ``0`` disables freshness checks
    (amr-only) and is allowed only with ``OYDP_OIDC_DEV_HTTP=1``. Production and
    any non-dev posture reject zero so amr-only never becomes a silent fallback.
    Negative or non-integer values fail closed as misconfiguration.
    """
    raw = os.getenv('OYDP_MFA_MAX_AGE_SECONDS')
    if raw is None or not raw.strip():
        return _DEFAULT_MFA_MAX_AGE_SECONDS
    try:
        value = int(raw.strip(), 10)
    except ValueError as exc:
        raise HTTPException(503, 'Invalid MFA freshness configuration') from exc
    if value < 0:
        raise HTTPException(503, 'Invalid MFA freshness configuration')
    if value == 0:
        if not loopback_oidc_dev_enabled():
            raise HTTPException(503, 'Invalid MFA freshness configuration')
        return None
    return value


def assert_mfa_configuration() -> None:
    """Fail closed at process start when MFA freshness is disabled outside local loopback OIDC."""
    raw = os.getenv('OYDP_MFA_MAX_AGE_SECONDS')
    if raw is not None and raw.strip() == '0' and not loopback_oidc_dev_enabled():
        raise RuntimeError(
            'OYDP_MFA_MAX_AGE_SECONDS=0 disables MFA freshness and is refused outside '
            'OYDP_OIDC_DEV_HTTP=1 local development'
        )
    # Exercise parsers so invalid ACR / max-age values fail before serving traffic.
    try:
        mfa_max_age_seconds()
        mfa_acr_values()
    except HTTPException as exc:
        raise RuntimeError(exc.detail) from exc


def mfa_acr_values() -> frozenset[str] | None:
    """Optional ACR allowlist. Unset means ACR is not required for MFA gates."""
    raw = os.getenv('OYDP_MFA_ACR_VALUES')
    if raw is None or not raw.strip():
        return None
    values = frozenset(item.strip() for item in raw.split(',') if item.strip())
    if not values:
        raise HTTPException(503, 'Invalid MFA ACR configuration')
    return values


def _as_unix_seconds(value) -> int:
    # Reject bool: isinstance(True, int) is True in Python.
    if type(value) is not int:
        raise jwt.InvalidTokenError('Invalid authentication time')
    if value < 0:
        raise jwt.InvalidTokenError('Invalid authentication time')
    return value


def verified_claims(authorization: str | None) -> dict:
    issuer = os.getenv('OIDC_ISSUER', '')
    audience = os.getenv('OIDC_AUDIENCE', '')
    url = os.getenv('OIDC_JWKS_URL', '')
    if not all((issuer, audience, url)):
        raise HTTPException(503, 'OIDC authentication not configured')
    # HTTPS is required in production. Loopback HTTP needs OYDP_OIDC_DEV_HTTP=1.
    if not endpoint_allowed(issuer) or not endpoint_allowed(url):
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
        if 'auth_time' in claims:
            claims['auth_time'] = _as_unix_seconds(claims['auth_time'])
        if 'acr' in claims and not isinstance(claims['acr'], str):
            raise jwt.InvalidTokenError('Invalid authentication context class')
        return claims
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, 'Identity provider unavailable') from None
    except jwt.PyJWTError:
        raise HTTPException(401, 'Invalid access token', headers={'WWW-Authenticate': 'Bearer'}) from None


def verified_subject(authorization: str | None = Header(default=None)) -> str:
    return verified_claims(authorization)['sub']


def require_mfa(authorization: str | None = Header(default=None)) -> bool:
    """Require an MFA method reference and, when configured, a fresh auth_time.

    IdP assumptions: access tokens carry ``amr`` with ``mfa`` and/or ``otp``, and
    when freshness is enabled they also carry integer ``auth_time`` (Unix seconds)
    from the authentication event. Optional ``OYDP_MFA_ACR_VALUES`` requires a
    matching string ``acr``. Mere presence of ``mfa``/``otp`` without a fresh
    ``auth_time`` is rejected when freshness is enabled (the default).
    """
    claims = verified_claims(authorization)
    if not _MFA_METHODS.intersection(claims.get('amr', [])):
        raise HTTPException(403, 'MFA access token required')
    allowed_acr = mfa_acr_values()
    if allowed_acr is not None:
        acr = claims.get('acr')
        if not isinstance(acr, str) or acr not in allowed_acr:
            raise HTTPException(403, 'Fresh MFA authentication required')
    max_age = mfa_max_age_seconds()
    if max_age is None:
        return True
    if 'auth_time' not in claims:
        raise HTTPException(403, 'Fresh MFA authentication required')
    auth_time = claims['auth_time']
    now = int(time.time())
    if auth_time > now:
        raise HTTPException(403, 'Fresh MFA authentication required')
    if now - auth_time > max_age:
        raise HTTPException(403, 'Fresh MFA authentication required')
    return True
