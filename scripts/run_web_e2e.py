"""Browser journey against loopback OIDC, the property API, and PostgreSQL.

Refuses to run unless OYDP_WEB_E2E_ALLOW=yes and TEST_DATABASE_URL names a
disposable database. Prints no passwords or access tokens.
"""
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.conninfo import make_conninfo

from scripts.migrate import migrate, provision_runtime

WEB = ROOT / 'apps' / 'web'


def require_disposable_database():
    if os.getenv('OYDP_WEB_E2E_ALLOW') != 'yes':
        raise SystemExit('Refusing to run: set OYDP_WEB_E2E_ALLOW=yes')
    dsn = os.environ['TEST_DATABASE_URL']
    name = dsn.rsplit('/', 1)[-1].split('?', 1)[0].lower()
    if 'e2e' not in name and 'test' not in name:
        raise SystemExit('Refusing to migrate a database whose name is not marked disposable')
    return dsn


def wait_for(url, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError('Timed out waiting for ' + url)


def spawn(command, env, cwd):
    return subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)


def stop(processes):
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)


def main():
    dsn = require_disposable_database()
    applied = migrate(dsn)
    password = 'web-e2e-runtime-' + secrets.token_hex(16)
    provision_runtime(dsn, password)
    tenant = str(uuid.uuid4())
    other = str(uuid.uuid4())
    with psycopg.connect(dsn) as conn:
        conn.execute("""
          DO $$
          DECLARE stmt text;
          BEGIN
            SELECT 'TRUNCATE TABLE ' || string_agg(format('%I.%I', schemaname, tablename), ', ') || ' RESTART IDENTITY CASCADE'
              INTO stmt
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename <> 'schema_migrations';
            IF stmt IS NOT NULL THEN
              EXECUTE stmt;
            END IF;
          END $$;
        """)
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id, subject_id, role) VALUES (%s,'alice','owner'),(%s,'mallory','owner')",
            (tenant, other),
        )
    print('Applied migrations:', ', '.join(applied) or 'none')
    issuer = 'http://127.0.0.1:9000'
    web = 'http://127.0.0.1:3000'
    base_env = os.environ.copy()
    oidc_env = base_env | {
        'OYDP_DEV_OIDC': '1',
        'OYDP_DEV_OIDC_ISSUER': issuer,
        'OYDP_DEV_OIDC_AUDIENCE': 'oydp-api',
        'OYDP_DEV_OIDC_CLIENT_ID': 'oydp-web',
        'OYDP_DEV_OIDC_REDIRECTS': web + '/callback',
    }
    storage = tempfile.mkdtemp(prefix='oydp-docs-')
    document_key = secrets.token_urlsafe(32)
    api_env = base_env | {
        'DATABASE_URL': make_conninfo(dsn, user='oydp_app', password=password),
        'OIDC_ISSUER': issuer,
        'OIDC_AUDIENCE': 'oydp-api',
        'OIDC_JWKS_URL': issuer + '/.well-known/jwks.json',
        'OYDP_OIDC_DEV_HTTP': '1',
        'DOCUMENT_STORAGE_DIR': storage,
        'DOCUMENT_STORAGE_KEY': document_key,
    }
    session_key = secrets.token_urlsafe(32)
    web_env = base_env | {
        'SESSION_KEY': session_key,
        'OIDC_ISSUER': issuer,
        'OIDC_CLIENT_ID': 'oydp-web',
        'OIDC_REDIRECT_URI': web + '/callback',
        'OIDC_AUDIENCE': 'oydp-api',
        'OIDC_JWKS_URL': issuer + '/.well-known/jwks.json',
        'OYDP_OIDC_DEV_HTTP': '1',
        'PROPERTY_API_BASE': 'http://127.0.0.1:8000',
        'PROPERTY_PAGE_SIZE': '1',
        'NEXT_TELEMETRY_DISABLED': '1',
    }
    processes = []
    try:
        subprocess.check_call(['npm', 'run', 'build'], cwd=WEB, env=web_env)
        processes.append(spawn([sys.executable, str(ROOT / 'tools' / 'dev_oidc.py')], oidc_env, ROOT))
        processes.append(spawn([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], api_env, ROOT / 'apps' / 'api'))
        processes.append(spawn(['npm', 'run', 'start', '--', '--hostname', '127.0.0.1', '--port', '3000'], web_env, WEB))
        wait_for(issuer + '/.well-known/openid-configuration')
        wait_for('http://127.0.0.1:8000/healthz')
        wait_for(web + '/')
        play_env = base_env | {
            'WEB_ORIGIN': web,
            'E2E_TENANT_ID': tenant,
            'E2E_OTHER_TENANT_ID': other,
        }
        result = subprocess.run(['npx', 'playwright', 'test'], cwd=WEB, env=play_env)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    finally:
        stop(processes)
        shutil.rmtree(storage, ignore_errors=True)


if __name__ == '__main__':
    main()
