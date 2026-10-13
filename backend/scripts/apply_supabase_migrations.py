"""Apply the repository's Supabase SQL files to SUPABASE_DB_URL.

Usage (only `psycopg` is required — no app imports):

    python scripts/apply_supabase_migrations.py [path-to-supabase-dir]

Files run in filename order, each inside its own transaction, and are tracked
in public._supabase_migrations so re-runs skip completed work. The database
URL comes from the SUPABASE_DB_URL environment variable or backend/.env.

Note: the direct Postgres endpoint of newer Supabase projects is IPv6-only.
Run this from a machine with IPv6 connectivity (your workstation), not from
an IPv4-only container.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg


def _db_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if url:
        return url
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("SUPABASE_DB_URL="):
                return line.split("=", 1)[1].strip()
    return ""


def _sql_files(root: Path) -> list[Path]:
    files = sorted((root / "migrations").glob("*.sql"))
    loose = root / "contact_submissions.sql"
    if loose.exists():
        files.append(loose)
    return files


def main() -> int:
    root = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[2] / "supabase"
    )
    db_url = _db_url()
    if not db_url:
        print("SUPABASE_DB_URL is not configured (set it in backend/.env)")
        return 1
    if not root.is_dir():
        print(f"SQL directory not found: {root}")
        return 1

    with psycopg.connect(db_url, connect_timeout=15) as conn:
        conn.execute(
            """create table if not exists public._supabase_migrations (
                   name text primary key,
                   applied_at timestamptz not null default now()
               )"""
        )
        for path in _sql_files(root):
            done = conn.execute(
                "select 1 from public._supabase_migrations where name = %s",
                (path.name,),
            ).fetchone()
            if done:
                print(f"skip   {path.name} (already applied)")
                continue
            print(f"apply  {path.name} ...", end=" ", flush=True)
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute(
                    "insert into public._supabase_migrations(name) values (%s)",
                    (path.name,),
                )
            print("ok")
    print("All Supabase SQL applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
