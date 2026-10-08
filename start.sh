#!/usr/bin/env bash
set -euo pipefail

# Create the pgvector extension when we can; ignore errors if it already exists
uv run python - <<'PY' || true
import os
import psycopg

url = os.environ.get("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://", 1)
if url:
    try:
        with psycopg.connect(url) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()
    except Exception as exc:
        print("Warning: could not create vector extension in Postgres:", exc)
PY

uv run alembic upgrade head
uv run uvicorn system.main:app --host 0.0.0.0 --port 8000
