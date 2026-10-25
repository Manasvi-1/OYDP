"""Pinned RS256 verifier. No token, tenant header or payload grants membership."""
from dataclasses import dataclass
from uuid import UUID
import jwt


@dataclass(frozen=True)
class Identity:
    subject: UUID
    mfa: bool


class TokenVerifier:
    def __init__(self, public_key: str, issuer: str, audience: str):
        if not issuer.startswith('https://') or not audience or 'PRIVATE KEY' in public_key:
            raise ValueError('HTTPS issuer, audience and public verification key required')
        self.key = jwt.algorithms.RSAAlgorithm.from_jwk(public_key) if public_key.startswith('{') else public_key
        self.issuer, self.audience = issuer, audience

    def verify(self, token: str) -> Identity:
        if len(token) > 16384:
            raise ValueError('Token too long')
        claims = jwt.decode(token, self.key, algorithms=['RS256'], issuer=self.issuer,
                            audience=self.audience, options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']})
        amr = claims.get('amr', [])
        if not isinstance(amr, list) or any(not isinstance(x, str) for x in amr):
            raise ValueError('Invalid authentication methods')
        # The configured issuer must contractually supply UUID subjects and the mfa AMR.
        return Identity(UUID(claims['sub']), 'mfa' in amr)
