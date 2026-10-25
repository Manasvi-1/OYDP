#!/bin/sh
# Synthetic, single-connection test DB only. Does not validate native concurrency or PostGIS.
set -eu
cd "$(dirname "$0")/.."
node tools/embedded-db/db.mjs &
OYDP_TEST_PID=$!
trap 'kill "$OYDP_TEST_PID" 2>/dev/null || true' EXIT
python - <<'PY'
import time, socket
for _ in range(120):
    try:
        with socket.create_connection(('127.0.0.1',55432), timeout=1): break
    except OSError: time.sleep(.25)
else: raise RuntimeError('Disposable database startup timed out')
PY
OYDP_TEST_ADMIN_DSN='postgresql://postgres@127.0.0.1:55432/postgres?sslmode=disable' \
OYDP_TEST_RUNTIME_DSN='postgresql://postgres@127.0.0.1:55432/postgres?sslmode=disable' \
OYDP_TEST_EMBEDDED=1 OYDP_TEST_ALLOW_RESET=yes python -m pytest -q
