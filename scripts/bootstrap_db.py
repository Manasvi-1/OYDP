"""Provision a NEW local database. Never imports credentials into committed files."""
import os
from pathlib import Path
import psycopg
from psycopg import sql

if os.environ.get('OYDP_LOCAL_BOOTSTRAP') != 'yes':
    raise SystemExit('Set OYDP_LOCAL_BOOTSTRAP=yes only for a new local development database')
password = os.environ['OYDP_RUNTIME_DB_PASSWORD']
if len(password) < 20:
    raise SystemExit('Use a randomly generated runtime password of at least 20 characters')
with psycopg.connect(os.environ['OYDP_ADMIN_DATABASE_URL'], autocommit=True) as conn:
    if conn.execute("SELECT to_regnamespace('oydp')").fetchone()[0] is not None:
        raise SystemExit('Schema already exists; refusing to overwrite')
    conn.execute(sql.SQL('CREATE ROLE oydp_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}').format(sql.Literal(password)))
    conn.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    conn.execute((Path(__file__).resolve().parents[1]/'migrations/001_foundation.up.sql').read_text())
print('Local schema initialized. Provision explicit memberships separately; no default user is authorized.')
