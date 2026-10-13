"""Supabase Postgres persistence, serialized per tenant for legacy store operations."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import threading
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb
from app.core.config import get_settings
from app.core.tenant import cloud, scope

_connection = ContextVar("store_connection", default=None)


@lru_cache(maxsize=1)
def pool() -> ConnectionPool:
    """Return a bounded process-wide pool for cloud database operations.

    Size this together with the maximum API and worker instance counts.
    prepare_threshold=None supports transaction-mode Postgres poolers.
    """
    settings = get_settings()
    return ConnectionPool(
        conninfo=settings.supabase_db_url,
        min_size=0,
        max_size=settings.supabase_db_pool_max_size,
        timeout=settings.supabase_db_pool_timeout_seconds,
        kwargs={"connect_timeout": 10, "prepare_threshold": None},
        name="mindmesh-postgres",
        open=True,
    )


def close_pool() -> None:
    """Close this process's database pool during graceful shutdown."""
    if pool.cache_info().currsize:
        pool().close()
        pool.cache_clear()


@contextmanager
def connect():
    existing = _connection.get()
    if existing is not None:
        yield existing
    else:
        with pool().connection() as conn:
            conn.execute("SET LOCAL statement_timeout = '30s'")
            yield conn


def member(tenant_id: str, user_id: str) -> bool:
    with connect() as conn:
        return conn.execute(
            """SELECT 1 FROM public.mm_memberships m
               WHERE m.tenant_id=%s AND m.user_id=%s AND m.active
                 AND NOT EXISTS (
                   SELECT 1 FROM public.mm_memberships other
                   WHERE other.tenant_id=m.tenant_id AND other.user_id<>m.user_id AND other.active
                 )""",
            (tenant_id, user_id),
        ).fetchone() is not None


class StoreLock:
    """Keep local locking; cloud mutations use a database transaction/advisory lock."""
    def __init__(self):
        self.local = threading.Lock()
        self.state = threading.local()

    def __enter__(self):
        if not cloud():
            return self.local.__enter__()
        db_pool = pool()
        conn = db_pool.getconn(timeout=get_settings().supabase_db_pool_timeout_seconds)
        try:
            conn.execute("SET LOCAL statement_timeout = '30s'")
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (scope().tenant_id,))
        except BaseException:
            conn.close()
            db_pool.putconn(conn)
            raise
        self.state.conn = conn
        self.state.pool = db_pool
        self.state.token = _connection.set(conn)
        return self

    def __exit__(self, kind, value, traceback):
        if not cloud():
            return self.local.__exit__(kind, value, traceback)
        conn = self.state.conn
        try:
            conn.rollback() if kind else conn.commit()
        finally:
            _connection.reset(self.state.token)
            self.state.pool.putconn(conn)


def load(kind: str, default: dict) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT body FROM public.mm_state WHERE tenant_id=%s AND kind=%s",
                           (scope().tenant_id, kind)).fetchone()
        return row[0] if row else default


def save(kind: str, data: dict) -> None:
    if _connection.get() is None:
        raise RuntimeError("Cloud state writes require a transaction")
    with connect() as conn:
        conn.execute("""INSERT INTO public.mm_state(tenant_id,kind,body) VALUES (%s,%s,%s)
                     ON CONFLICT(tenant_id,kind) DO UPDATE SET body=excluded.body""",
                     (scope().tenant_id, kind, Jsonb(data)))


def quota_add(tenant_id: str, kind: str, day: str, amount: int) -> int:
    """Atomically add amount to a daily quota counter. Returns the new total.

    One UPSERT per call — concurrent API replicas share exact usage without
    per-unit timestamp rows (the Redis-less replacement for INCRBY).
    """
    with connect() as conn:
        row = conn.execute(
            """INSERT INTO public.mm_quotas(tenant_id, kind, day, used, updated_at)
               VALUES (%s,%s,%s,%s,now())
               ON CONFLICT (tenant_id, kind, day)
               DO UPDATE SET used = public.mm_quotas.used + EXCLUDED.used, updated_at=now()
               RETURNING used""",
            (tenant_id, kind, day, amount),
        ).fetchone()
        conn.commit()
        return int(row[0])


@contextmanager
def resource_lock(tenant_id: str, resource_id: str):
    """Serialize ingestion of the same resource (replaces the Redis lock).

    Non-blocking PostgreSQL advisory lock held to transaction commit; raises
    ConnectionError("Resource busy") when another worker holds it so the job
    is requeued with backoff exactly like the Redis path.
    """
    key = f"{tenant_id}:{resource_id}"
    with connect() as conn:
        conn.execute("SET LOCAL statement_timeout = '30s'")
        for _ in range(5):
            row = conn.execute(
                "SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0))", (key,)
            ).fetchone()
            if row and row[0]:
                break
            import time as _time

            _time.sleep(0.2)
        else:
            raise ConnectionError("Resource busy")
        yield
        conn.commit()


def save_result(job: dict) -> None:
    owner = scope()
    with connect() as conn:
        conn.execute("""INSERT INTO public.mm_job_results(job_id,tenant_id,user_id,resource_id,body)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(job_id) DO UPDATE SET body=excluded.body
            WHERE mm_job_results.tenant_id=excluded.tenant_id AND mm_job_results.user_id=excluded.user_id""",
            (owner.job_id, owner.tenant_id, owner.user_id, owner.resource_id, Jsonb(job)))
