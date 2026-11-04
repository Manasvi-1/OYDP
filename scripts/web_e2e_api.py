"""Disposable browser acceptance server. Never part of the application startup path.

Only the JWKS network transport is substituted with an ephemeral RSA public key.
Production JWT signature/claims, API handlers, restricted DB role and RLS run unchanged.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import jwt
import psycopg
from psycopg.conninfo import make_conninfo
from cryptography.hazmat.primitives.asymmetric import rsa

from scripts.migrate import migrate, provision_runtime

if os.getenv('OYDP_BROWSER_DISPOSABLE') != 'yes':
    raise SystemExit('Explicit disposable browser database opt-in required')
dsn = os.environ['TEST_DATABASE_URL']
from psycopg.conninfo import conninfo_to_dict
if conninfo_to_dict(dsn).get('dbname') != 'oydp_web_e2e':
    raise SystemExit('Only the dedicated oydp_web_e2e database is allowed')
password = 'disposable-browser-runtime-password'
migrate(dsn)
provision_runtime(dsn, password)
tenant = UUID('11111111-1111-1111-1111-111111111111')
other = UUID('22222222-2222-2222-2222-222222222222')
with psycopg.connect(dsn) as conn:
    conn.execute("INSERT INTO tenant_memberships VALUES (%s,'browser-owner','owner'),(%s,'browser-reader','viewer'),(%s,'browser-outsider','owner') ON CONFLICT DO NOTHING", (tenant,tenant,other))
os.environ['DATABASE_URL'] = make_conninfo(dsn, user='oydp_app', password=password)
os.environ['OIDC_ISSUER'] = 'https://browser-test.invalid'
os.environ['OIDC_AUDIENCE'] = 'oydp-api'
os.environ['OIDC_JWKS_URL'] = 'https://browser-test.invalid/jwks'
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
now = datetime.now(timezone.utc)
def token(subject, mfa=True):
    return jwt.encode({'iss':os.environ['OIDC_ISSUER'],'aud':'oydp-api','sub':subject,
        'iat':now,'exp':now+timedelta(minutes=15),'amr':['mfa'] if mfa else []}, key,
        algorithm='RS256',headers={'typ':'at+jwt','kid':'ephemeral-browser-key'})
path = Path('apps/web/.e2e/credentials.json')
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps({'tenant':str(tenant),'owner':token('browser-owner'),
    'reader':token('browser-reader'),'outsider':token('browser-outsider'),
    'withoutMfa':token('browser-owner', False)}))
path.chmod(0o600)
from app import auth
class EphemeralKeys:
    def get_signing_key_from_jwt(self, raw):
        return SimpleNamespace(key=key.public_key())
auth.jwks_client = lambda url: EphemeralKeys()
from app.main import app
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=8000, access_log=False)
