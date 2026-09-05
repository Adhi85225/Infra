#!/bin/sh
# =============================================================================
# API container startup.
#
#   1. wait for PostgreSQL
#   2. apply database migrations
#   3. seed the role/module catalogue and the bootstrap Super Admin
#   4. start the server
#
# Every step is idempotent, so restarting the container is always safe.
# =============================================================================
set -eu

echo "[entrypoint] waiting for the database..."
python - <<'PY'
import asyncio, os, sys, time
from urllib.parse import urlsplit

import asyncpg

url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
deadline = time.time() + 90

async def wait() -> None:
    last = None
    while time.time() < deadline:
        try:
            conn = await asyncpg.connect(url, timeout=5)
            await conn.close()
            print("[entrypoint] database is ready")
            return
        except Exception as exc:
            last = exc
            await asyncio.sleep(2)
    print(f"[entrypoint] database unreachable after 90s: {last}", file=sys.stderr)
    sys.exit(1)

asyncio.run(wait())
PY

echo "[entrypoint] applying migrations..."
alembic upgrade head

echo "[entrypoint] seeding roles, modules and permissions..."
python -m app.db.seed

echo "[entrypoint] starting API on 0.0.0.0:8000"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-2}" \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --no-access-log
