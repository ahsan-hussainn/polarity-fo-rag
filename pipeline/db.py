"""Database access + migrations for the Supabase Postgres store (ADR-0002, ADR-0006).

Design (deliberately lightweight, consistent with the medallion ADR):
  - Direct Postgres via psycopg3, not the Supabase REST client: the pipeline does DDL and bulk
    inserts, which are awkward over PostgREST and natural over a real connection.
  - Migrations are plain, ordered, idempotent .sql files applied by the tiny runner below, not
    Alembic or the Supabase CLI: no heavy tooling for a 50-record dataset, and the SQL stays
    readable as a graded deliverable.

Connection: reads DATABASE_URL from .env (gitignored). Use Supabase's *Session pooler* string
(IPv4, port 5432) -- the direct connection is IPv6-only, and the transaction pooler (6543) breaks
the prepared statements psycopg relies on.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib

import psycopg

try:  # load .env if python-dotenv is installed; harmless if not
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "db" / "migrations"


def get_dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and paste your Supabase "
            "Session pooler connection string (Dashboard -> Connect -> Session pooler)."
        )
    return dsn


def get_conn() -> psycopg.Connection:
    return psycopg.connect(get_dsn())


# --- Pooled connections for the serving path (ADR-0017) -------------------------------------
# Each psycopg.connect() to the Supabase pooler pays ~1s of TLS handshake -- fine for batch
# pipeline stages, unacceptable per web request. The pool keeps connections open and hands them
# out safely across FastAPI's worker threads (a bare cached connection would NOT be thread-safe).
# Serving is read-only, so connections are autocommit: no transaction state to leak between
# requests. check=idle-reconnect is handled by the pool itself.
_pool = None


def get_pool():
    global _pool
    if _pool is None:
        from psycopg_pool import ConnectionPool

        _pool = ConnectionPool(
            get_dsn(), min_size=0, max_size=4, open=True,
            kwargs={"autocommit": True},
            check=ConnectionPool.check_connection,  # revalidate idle conns (pooler drops them)
        )
    return _pool


def check() -> dict:
    """Verify connectivity and report extensions + medallion schemas present."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("select current_database(), current_user, version()")
        db, user, version = cur.fetchone()
        cur.execute("select extname from pg_extension where extname in ('vector', 'pg_trgm')")
        exts = sorted(r[0] for r in cur.fetchall())
        cur.execute("select nspname from pg_namespace where nspname in ('bronze', 'silver', 'gold')")
        schemas = sorted(r[0] for r in cur.fetchall())
    return {
        "database": db,
        "user": user,
        "version": version.split(" on ")[0],
        "extensions": exts,
        "schemas": schemas,
    }


def apply_migrations() -> list[str]:
    """Apply every db/migrations/*.sql not yet recorded, in filename order. Idempotent."""
    applied: list[str] = []
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "create table if not exists public.schema_migrations ("
            " filename text primary key, applied_at timestamptz not null default now())"
        )
        conn.commit()
        cur.execute("select filename from public.schema_migrations")
        done = {r[0] for r in cur.fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            cur.execute(path.read_text(encoding="utf-8"))  # no params -> multi-statement OK
            cur.execute("insert into public.schema_migrations(filename) values (%s)", (path.name,))
            conn.commit()
            applied.append(path.name)
    return applied


def insert_captures(rows: list[dict]) -> int:
    """Append raw records to bronze.captures. Each row: {source, raw, source_url?, entity_key?,
    fetched_at?}. Dedupes on (source, sha256(source|raw)); re-running a load is a no-op."""
    inserted = 0
    with get_conn() as conn, conn.cursor() as cur:
        for r in rows:
            raw_json = json.dumps(r["raw"], sort_keys=True, ensure_ascii=False)
            content_hash = hashlib.sha256(f"{r['source']}|{raw_json}".encode("utf-8")).hexdigest()
            cur.execute(
                "insert into bronze.captures"
                " (source, source_url, entity_key, fetched_at, raw, content_hash)"
                " values (%s, %s, %s, %s, %s::jsonb, %s)"
                " on conflict (source, content_hash) do nothing",
                (r["source"], r.get("source_url"), r.get("entity_key"),
                 r.get("fetched_at"), raw_json, content_hash),
            )
            inserted += cur.rowcount
        conn.commit()
    return inserted
