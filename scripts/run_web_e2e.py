"""Browser journey against loopback OIDC, the property API, and PostgreSQL.

Refuses to run unless OYDP_WEB_E2E_ALLOW=yes and TEST_DATABASE_URL names a
disposable database. Prints no passwords or access tokens.
"""
import base64
import os
import secrets
import shutil
import signal
import socket
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


def resolve_cmd(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    if os.name == 'nt':
        found = shutil.which(f'{name}.cmd') or shutil.which(f'{name}.exe')
        if found:
            return found
    raise SystemExit(f'Required command not found on PATH: {name}')


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


def port_bindable(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            return False
    return True


def ensure_port_free(port: int, timeout: float = 45):
    """Kill stale owners when possible, then require a successful bind."""
    if os.name == 'nt':
        listed = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue |"
             f" Select-Object -ExpandProperty OwningProcess) -join ','"],
            capture_output=True, text=True, check=False,
        )
        # OwningProcess 0/4 are Windows phantoms after abrupt kills.
        pids = [
            part.strip()
            for part in (listed.stdout or '').split(',')
            if part.strip().isdigit() and part.strip() not in {'0', '4'}
        ]
        for pid in pids:
            subprocess.run(['taskkill', '/PID', pid, '/T', '/F'], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(['bash', '-lc', f'fuser -k {port}/tcp >/dev/null 2>&1 || true'], check=False)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_bindable(port):
            return
        time.sleep(0.5)
    raise SystemExit(f'Port {port} is still in use after cleanup; refusing to start e2e')


def spawn(command, env, cwd):
    kwargs = {'cwd': cwd, 'env': env}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs['start_new_session'] = True
    return subprocess.Popen(command, **kwargs)


def _terminate(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(
            ['taskkill', '/PID', str(process.pid), '/T', '/F'],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def stop(processes):
    for process in processes:
        _terminate(process)
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _terminate(process)
            process.wait(timeout=5)


def reset_disposable_tables(conn):
    # Disposable reset only. Append-only audit_ledger triggers block ordinary TRUNCATE.
    conn.execute("""
      DO $$
      DECLARE stmt text;
      BEGIN
        PERFORM set_config('session_replication_role', 'replica', true);
        SELECT 'TRUNCATE TABLE ' || string_agg(format('%I.%I', schemaname, tablename), ', ') || ' RESTART IDENTITY CASCADE'
          INTO stmt
        FROM pg_tables
        WHERE schemaname = 'public' AND tablename <> 'schema_migrations';
        IF stmt IS NOT NULL THEN
          EXECUTE stmt;
        END IF;
        PERFORM set_config('session_replication_role', 'origin', true);
      END $$;
    """)


def main():
    dsn = require_disposable_database()
    applied = migrate(dsn)
    password = 'web-e2e-runtime-' + secrets.token_hex(16)
    provision_runtime(dsn, password)
    tenant = str(uuid.uuid4())
    other = str(uuid.uuid4())
    with psycopg.connect(dsn) as conn:
        reset_disposable_tables(conn)
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id, subject_id, role) VALUES (%s,'alice','owner'),(%s,'mallory','owner')",
            (tenant, other),
        )
    print('Applied migrations:', ', '.join(applied) or 'none')
    web_port = int(os.getenv('OYDP_WEB_E2E_PORT', '3000'))
    api_port = int(os.getenv('OYDP_API_E2E_PORT', '8000'))
    oidc_port = int(os.getenv('OYDP_OIDC_E2E_PORT', '9000'))

    def choose_port(preferred: int, label: str) -> int:
        # Windows Hyper-V / abrupt kills can reserve or ghost common loopback ports.
        for candidate in [preferred, *range(preferred + 1, preferred + 30)]:
            if port_bindable(candidate):
                if candidate != preferred:
                    print(f'{label} port {preferred} not bindable; using {candidate}')
                return candidate
        raise SystemExit(f'No bindable {label} port near {preferred}')

    web_port = choose_port(web_port, 'web')
    api_port = choose_port(api_port, 'api')
    oidc_port = choose_port(oidc_port, 'oidc')
    issuer = f'http://127.0.0.1:{oidc_port}'
    web = f'http://127.0.0.1:{web_port}'
    api = f'http://127.0.0.1:{api_port}'
    base_env = os.environ.copy()
    oidc_env = base_env | {
        'OYDP_DEV_OIDC': '1',
        'OYDP_DEV_OIDC_ISSUER': issuer,
        'OYDP_DEV_OIDC_AUDIENCE': 'oydp-api',
        'OYDP_DEV_OIDC_CLIENT_ID': 'oydp-web',
        'OYDP_DEV_OIDC_REDIRECTS': web + '/callback',
    }
    storage = tempfile.mkdtemp(prefix='oydp-docs-')
    # Exactly 32 raw bytes, standard urlsafe base64 (with padding) for DOCUMENT_STORAGE_KEY.
    document_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii')
    api_env = base_env | {
        'DATABASE_URL': make_conninfo(dsn, user='oydp_app', password=password),
        'OIDC_ISSUER': issuer,
        'OIDC_AUDIENCE': 'oydp-api',
        'OIDC_JWKS_URL': issuer + '/.well-known/jwks.json',
        'OYDP_OIDC_DEV_HTTP': '1',
        'DOCUMENT_STORAGE_DIR': storage,
        'DOCUMENT_STORAGE_KEY': document_key,
    }
    session_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii').rstrip('=')
    web_env = base_env | {
        'SESSION_KEY': session_key,
        'OIDC_ISSUER': issuer,
        'OIDC_CLIENT_ID': 'oydp-web',
        'OIDC_REDIRECT_URI': web + '/callback',
        'OIDC_AUDIENCE': 'oydp-api',
        'OIDC_JWKS_URL': issuer + '/.well-known/jwks.json',
        'OYDP_OIDC_DEV_HTTP': '1',
        # next start sets NODE_ENV=production; keep cookies usable on loopback HTTP.
        'OYDP_COOKIE_SECURE': '0',
        'PROPERTY_API_BASE': api,
        'PROPERTY_PAGE_SIZE': '1',
        'NEXT_TELEMETRY_DISABLED': '1',
        'PORT': str(web_port),
    }
    npm = resolve_cmd('npm')
    npx = resolve_cmd('npx')
    for port in (web_port, api_port, oidc_port):
        ensure_port_free(port)
    processes = []
    try:
        build = subprocess.run([npm, 'run', 'build'], cwd=WEB, env=web_env)
        if build.returncode != 0:
            # Windows e2e can race a stale .next tree; one clean retry is enough.
            shutil.rmtree(WEB / '.next', ignore_errors=True)
            subprocess.check_call([npm, 'run', 'build'], cwd=WEB, env=web_env)
        processes.append(spawn([sys.executable, str(ROOT / 'tools' / 'dev_oidc.py')], oidc_env, ROOT))
        processes.append(spawn([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(api_port)], api_env, ROOT / 'apps' / 'api'))
        # Bypass package.json hardcoded --port 3000 so ghost sockets can fall back.
        processes.append(spawn([npx, 'next', 'start', '--hostname', '127.0.0.1', '--port', str(web_port)], web_env, WEB))
        wait_for(issuer + '/.well-known/openid-configuration')
        wait_for(api + '/healthz')
        wait_for(web + '/')
        play_env = base_env | {
            'WEB_ORIGIN': web,
            'E2E_TENANT_ID': tenant,
            'E2E_OTHER_TENANT_ID': other,
        }
        # Journey covers sign-in through property/document/diligence/audit against the disposable DB.
        result = subprocess.run([npx, 'playwright', 'test', 'e2e/journey.spec.mjs'], cwd=WEB, env=play_env)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    finally:
        stop(processes)
        shutil.rmtree(storage, ignore_errors=True)


if __name__ == '__main__':
    main()
