"""Google Cloud backend: config validators, Gemini embeddings, Postgres jobs,
Cloud Tasks dispatch, dispatcher auth, Groq transcription and spool uploads.

Everything here is hermetic: HTTP and Postgres are faked in-process, so the
suite passes with no cloud credentials and no network (mirrors CI).
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.tenant import Scope, current_scope
from app.services import embeddings


# --- helpers ---------------------------------------------------------------

@contextmanager
def as_user(tenant: str, user: str):
    token = current_scope.set(Scope(tenant, user))
    try:
        yield
    finally:
        current_scope.reset(token)


TENANT = "11111111-1111-1111-1111-111111111111"
USER = "22222222-2222-2222-2222-222222222222"


def gcp_kwargs(**overrides):
    base = dict(
        mindmesh_execution_mode="cloud",
        job_backend="gcp",
        supabase_url="https://xyz.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_db_url="postgresql://u:p@host/db?sslmode=require",
        qdrant_url="https://xyz.qdrant.io",
        qdrant_api_key="qdrant",
        qdrant_collection="mindmesh_gemini_v1",
        embedding_provider="gemini",
        embedding_model="gemini-embedding-2",
        embedding_dim=768,
        gemini_api_key="gemini-test",
        llm_provider="groq",
        groq_api_key="groq-test",
        cors_origins="https://example.com",
        gcp_project_id="proj",
        gcp_region="region",
        cloud_tasks_queue="mindmesh-jobs",
        cloud_tasks_dispatcher_url="https://dispatcher.example.com",
        cloud_tasks_service_account="tasks@proj.iam.gserviceaccount.com",
        cloud_tasks_dispatch_secret="secret",
        cloud_run_job_name="mindmesh-worker",
    )
    base.update(overrides)
    return base


@pytest.fixture
def cloud_mode(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "job_backend", "postgres")
    return cfg


# --- config ----------------------------------------------------------------

def test_gcp_settings_validate_without_redis():
    settings = Settings(**gcp_kwargs(redis_url=""))
    assert settings.job_backend == "gcp"
    assert settings.embedding_dim_for_model == 768
    assert settings.embedding_label == "gemini:gemini-embedding-2"


def test_gcp_settings_reject_missing_gemini_key():
    with pytest.raises(ValueError):
        Settings(**gcp_kwargs(gemini_api_key=""))


def test_gcp_settings_reject_missing_gcp_fields():
    with pytest.raises(ValueError):
        Settings(**gcp_kwargs(gcp_project_id=""))


def test_gcp_settings_reject_legacy_collection():
    with pytest.raises(ValueError):
        Settings(**gcp_kwargs(qdrant_collection="mindmesh"))


def test_cloud_redis_backend_still_requires_redis():
    with pytest.raises(ValueError):
        Settings(**gcp_kwargs(job_backend="redis", redis_url="",
                              embedding_provider="ollama", embedding_model="nomic-embed-text"))


def test_modal_label_unchanged():
    settings = Settings(**gcp_kwargs(
        mindmesh_execution_mode="modal", job_backend="redis", redis_url="rediss://h:1",
        embedding_provider="ollama", embedding_model="bge-m3", embedding_dim=1024,
        qdrant_collection="mindmesh_bge_m3_v1"))
    assert settings.embedding_label == "BAAI/bge-m3"


# --- Gemini embeddings -----------------------------------------------------

class _FakeEmbedResponse:
    def __init__(self, vectors):
        self.status_code = 200
        self._vectors = vectors
        self.text = ""

    def json(self):
        return {"embeddings": [{"values": v} for v in self._vectors]}


class _FakeGeminiClient:
    seen: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).seen.append(json)
        assert ":batchEmbedContents" in url
        assert headers["x-goog-api-key"] == "gemini-test"
        dim = 768
        vectors = [[float(i)] * dim for i, _ in enumerate(json["requests"])]
        return _FakeEmbedResponse(vectors)


@pytest.fixture
def gemini(monkeypatch):
    embeddings.reset_cache_for_tests()
    _FakeGeminiClient.seen = []
    cfg = get_settings()
    monkeypatch.setattr(cfg, "embedding_provider", "gemini")
    monkeypatch.setattr(cfg, "embedding_model", "gemini-embedding-2")
    monkeypatch.setattr(cfg, "embedding_dim", 768)
    monkeypatch.setattr(cfg, "gemini_api_key", "gemini-test")
    monkeypatch.setattr(httpx, "AsyncClient", _FakeGeminiClient)
    yield cfg
    embeddings.reset_cache_for_tests()


@pytest.mark.anyio
async def test_gemini_embeds_each_chunk_separately(gemini):
    vectors = await embeddings.embed_texts(["alpha", "beta", "gamma"])
    assert len(vectors) == 3
    assert vectors[0] != vectors[1] != vectors[2]
    # One request entry per chunk — never one aggregated vector for a batch.
    assert len(_FakeGeminiClient.seen) == 1
    assert len(_FakeGeminiClient.seen[0]["requests"]) == 3
    assert all(r["taskType"] == "RETRIEVAL_DOCUMENT" for r in _FakeGeminiClient.seen[0]["requests"])


@pytest.mark.anyio
async def test_gemini_query_uses_retrieval_query(gemini):
    await embeddings.embed_text("what is mindmesh?", purpose="query")
    assert _FakeGeminiClient.seen[0]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


@pytest.mark.anyio
async def test_gemini_refuses_partial_or_wrong_dim_batches(gemini, monkeypatch):
    class _Short(_FakeGeminiClient):
        async def post(self, url, json=None, headers=None):
            return _FakeEmbedResponse([[1.0] * 768])  # 1 vector for 2 texts

    monkeypatch.setattr(httpx, "AsyncClient", _Short)
    with pytest.raises(RuntimeError):
        await embeddings.embed_texts(["one", "two"])

    class _WrongDim(_FakeGeminiClient):
        async def post(self, url, json=None, headers=None):
            return _FakeEmbedResponse([[1.0] * 1024, [2.0] * 1024])

    monkeypatch.setattr(httpx, "AsyncClient", _WrongDim)
    with pytest.raises(RuntimeError):
        await embeddings.embed_texts(["three", "four"])


@pytest.mark.anyio
async def test_gemini_cache_separates_purpose(gemini):
    doc = await embeddings.embed_text("same text", purpose="document")
    query = await embeddings.embed_text("same text", purpose="query")
    assert doc == query  # fake returns identical values; two API calls prove no key collision
    assert len(_FakeGeminiClient.seen) == 2


# --- Postgres jobs (faked connection) --------------------------------------

class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


def _unwrap(value):
    return value.obj if type(value).__name__ == "Jsonb" else value


class _FakePG:
    """Minimal in-memory mm_jobs/mm_quotas stand-in behind the psycopg API."""

    def __init__(self):
        self.jobs = {}
        self.quotas = {}
        self._last = _FakeResult([])

    def _row(self, job):
        return (job["job_id"], job["tenant_id"], job["user_id"], job["resource_id"],
                job["job_type"], job["payload"], job["fingerprint"], job["status"],
                job["attempts"], job.get("lease"), job.get("next_at"),
                job.get("result"), job.get("error"), job["created_at"])

    # connection API
    @contextmanager
    def cursor(self):
        yield self

    def commit(self):
        pass

    def fetchone(self):
        return self._last.fetchone()

    def fetchall(self):
        return self._last.fetchall()

    def execute(self, sql, params=()):
        self._last = self._run(sql, params)
        return self._last

    def _run(self, sql, params=()):
        head = " ".join(sql.split())[:60]
        if head.startswith("SELECT pg_advisory_xact_lock"):
            return _FakeResult([(0,)])
        if head.startswith("SELECT job_id, tenant_id"):
            job = self.jobs.get(str(params[0]))
            return _FakeResult([self._row(job)] if job else [])
        if head.startswith("INSERT INTO public.mm_jobs"):
            job_id = str(params[0])
            if job_id in self.jobs:
                return _FakeResult([])
            now = time.time()
            self.jobs[job_id] = {
                "job_id": job_id, "tenant_id": str(params[1]), "user_id": str(params[2]),
                "resource_id": params[3], "job_type": params[4], "payload": _unwrap(params[5]),
                "fingerprint": params[6], "status": "queued", "attempts": 0, "created_at": now,
            }
            return _FakeResult([(params[6],)])
        if head.startswith("SELECT fingerprint FROM"):
            job = self.jobs.get(str(params[0]))
            return _FakeResult([(job["fingerprint"],)] if job else [])
        if "RETURNING job_id" in sql:
            stale_after = params[0]
            revived = [(j["job_id"],) for j in self.jobs.values()
                       if j["status"] == "processing" and j.get("next_at", 0) < time.time() - stale_after]
            for (job_id,) in revived:
                self.jobs[job_id].update(status="queued", next_at=time.time())
                self.jobs[job_id].pop("lease", None)
            return _FakeResult(revived)
        if head.startswith("UPDATE public.mm_jobs SET status"):
            status, attempts, lease, next_at, result, error, dlq, job_id = params
            job = self.jobs[str(job_id)]
            job.update(status=status, attempts=attempts, next_at=float(next_at))
            if lease is not None:
                job["lease"] = lease
            if result is not None:
                job["result"] = _unwrap(result)
            if error is not None:
                job["error"] = _unwrap(error)
            return _FakeResult([])
        if "SELECT job_id FROM public.mm_jobs WHERE status='queued'" in " ".join(sql.split()):
            due = [j for j in self.jobs.values()
                   if j["status"] == "queued" and j.get("next_at", 0) <= time.time()]
            due.sort(key=lambda j: j.get("next_at", 0))
            return _FakeResult([(due[0]["job_id"],)] if due else [])
        if head.startswith("SELECT count(*) FROM public.mm_jobs WHERE tenant_id"):
            n = sum(1 for j in self.jobs.values() if j["tenant_id"] == str(params[0]))
            return _FakeResult([(n,)])
        if head.startswith("SELECT count(*) FROM public.mm_jobs WHERE status NOT IN"):
            n = sum(1 for j in self.jobs.values() if j["status"] not in {"completed", "failed", "cancelled"})
            return _FakeResult([(n,)])
        if head.startswith("SELECT count(*) FROM public.mm_jobs WHERE dlq"):
            return _FakeResult([(0,)])
        if head.startswith("INSERT INTO public.mm_quotas"):
            key = (str(params[0]), params[1], params[2])
            self.quotas[key] = self.quotas.get(key, 0) + params[3]
            return _FakeResult([(self.quotas[key],)])
        raise AssertionError(f"unexpected SQL: {sql[:80]}")


@pytest.fixture
def pg(monkeypatch, cloud_mode):
    from app.services import cloud_db

    fake = _FakePG()

    @contextmanager
    def fake_connect():
        yield fake

    monkeypatch.setattr(cloud_db, "connect", fake_connect)
    return fake


def test_pg_job_lifecycle(pg):
    from app.services import jobs

    with as_user(TENANT, USER):
        job = jobs.create("chat", {"question": "hi"}, "res-1", "idem-1")
        assert job["status"] == "queued"
        same = jobs.create("chat", {"question": "hi"}, "res-1", "idem-1")
        assert same["job_id"] == job["job_id"]
        with pytest.raises(ValueError):
            jobs.create("chat", {"question": "other"}, "res-1", "idem-1")
        claimed, lease = jobs.claim(job["job_id"])
        assert claimed["status"] == "processing"
        with pytest.raises(PermissionError):
            jobs.claim(job["job_id"])
        done = jobs.finish(job["job_id"], lease, result={"answer": "hello"})
        assert done["status"] == "completed"
        assert jobs.owned(job["job_id"])["job_id"] == job["job_id"]


def test_pg_cancel_replay_and_reconcile(pg):
    from app.services import jobs

    with as_user(TENANT, USER):
        job = jobs.create("search", {"query": "x"}, "res-2")
        jobs.cancel(job["job_id"])
        assert jobs.raw(job["job_id"])["status"] == "cancelled"
        with pytest.raises(ValueError):
            jobs.replay(job["job_id"])
        doomed = jobs.create("search", {"query": "y"}, "res-3")
        claimed, lease = jobs.claim(doomed["job_id"])
        failed = jobs.finish(doomed["job_id"], lease,
                             error={"error_code": "X", "message": "boom", "retryable": False})
        assert failed["status"] == "failed"
        back = jobs.replay(doomed["job_id"])
        assert back["status"] == "queued" and back["attempts"] == 0
        with pytest.raises(PermissionError):
            jobs.finish(doomed["job_id"], "stale-lease", result={})


def test_pg_reconcile_requeues_stale_processing(pg):
    from app.services import jobs

    with as_user(TENANT, USER):
        job = jobs.create("web", {"url": "https://example.com"}, "res-4")
        jobs.claim(job["job_id"])
        pg.jobs[job["job_id"]]["next_at"] = time.time() - 5000
        stats = jobs.reconcile()
        assert stats.get("requeued") == 1
        assert jobs.raw(job["job_id"])["status"] == "queued"


def test_pg_peek_due_returns_next_job(pg):
    from app.services import jobs, jobs_pg

    with as_user(TENANT, USER):
        assert jobs_pg.peek_due() is None
        job = jobs.create("web", {"url": "https://example.com"}, "res-8")
        assert jobs_pg.peek_due() == job["job_id"]


def test_pg_cross_tenant_hidden(pg):
    from app.services import jobs

    with as_user(TENANT, USER):
        job = jobs.create("chat", {"question": "secret"}, "res-5")
    with as_user(TENANT, "33333333-3333-3333-3333-333333333333"):
        with pytest.raises(KeyError):
            jobs.owned(job["job_id"])


def test_pg_quota_exhaustion(pg, monkeypatch, cloud_mode):
    from app.services import jobs

    monkeypatch.setattr(cloud_mode, "max_jobs_per_tenant_per_day", 1)
    with as_user(TENANT, USER):
        jobs.create("chat", {"question": "one"}, "res-6")
        with pytest.raises(jobs.QuotaExceeded):
            jobs.create("chat", {"question": "two"}, "res-7")


# --- Postgres quota counters -----------------------------------------------

def test_quota_hit_uses_postgres_in_cloud(monkeypatch):
    from app.core import ratelimit
    from app.services import cloud_db

    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "supabase_db_url", "postgresql://u:p@host/db?sslmode=require")
    monkeypatch.setattr(cfg, "redis_url", "")
    calls = []
    monkeypatch.setattr(cloud_db, "quota_add", lambda *a: calls.append(a) or 41)
    allowed, used = ratelimit.quota_hit(TENANT, "upload_bytes", 1024, 100)
    assert (allowed, used) == (True, 41)
    assert calls[0][:3] == (TENANT, "upload_bytes", time.strftime("%Y%m%d"))


def test_quota_add_sql(pg):
    from app.services import cloud_db

    # Only asserts the UPSERT shape executes and returns the new total.
    assert cloud_db.quota_add(TENANT, "jobs", time.strftime("%Y%m%d"), 3) == 3


# --- Cloud Tasks ------------------------------------------------------------

class _FakeTasksPost:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"name": "projects/p/locations/r/queues/q/tasks/1"}
        self.text = ""
        self.seen = []

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_cloud_tasks_enqueue_shape(monkeypatch):
    import httpx as httpx_module
    from app.services import cloud_tasks

    cfg = get_settings()
    for key, value in gcp_kwargs().items():
        if hasattr(cfg, key):
            monkeypatch.setattr(cfg, key, value)
    posted = []

    def fake_post(url, headers=None, json=None, timeout=None):
        posted.append((url, headers, json))
        return _FakeTasksPost()

    def fake_get(url, headers=None, timeout=None):
        class _Tok:
            def raise_for_status(self):
                pass

            def json(self):
                return {"access_token": "tok"}

        return _Tok()

    monkeypatch.setattr(httpx_module, "post", fake_post)
    monkeypatch.setattr(httpx_module, "get", fake_get)
    job_id = str(uuid.uuid4())
    name = cloud_tasks.enqueue(job_id)
    assert name.endswith("/tasks/1")
    url, headers, body = posted[0]
    assert "queues/mindmesh-jobs/tasks" in url
    assert headers["Authorization"] == "Bearer tok"
    req = body["task"]["httpRequest"]
    assert req["url"] == f"https://dispatcher.example.com/dispatch/{job_id}"
    assert req["oidcToken"]["serviceAccountEmail"] == "tasks@proj.iam.gserviceaccount.com"
    assert req["headers"] == {"X-Dispatch-Secret": "secret"}


def test_cloud_tasks_unavailable_leaves_job_queued(monkeypatch):
    import httpx as httpx_module
    from app.services import cloud_tasks

    def boom(url, headers=None, timeout=None):
        raise httpx_module.ConnectError("no metadata")

    monkeypatch.setattr(httpx_module, "get", boom)
    assert cloud_tasks.enqueue_best_effort(str(uuid.uuid4())) is None


# --- dispatcher -------------------------------------------------------------

@pytest.fixture
def dispatcher_client(monkeypatch):
    import types

    from app import dispatcher
    from app.services import jobs

    cfg = get_settings()
    monkeypatch.setattr(cfg, "cloud_tasks_dispatch_secret", "secret")
    # Simulate a freshly started dispatcher process: with a real monotonic clock
    # that has already run past the launch guard, the "never launched" path
    # would silently pass even with a broken guard (it failed only on CI's
    # fresh VMs before).
    monkeypatch.setattr(dispatcher, "time", types.SimpleNamespace(monotonic=lambda: 100.0))
    store = {"job": {"job_id": "j", "status": "queued"}, "launched": []}
    monkeypatch.setattr(jobs, "raw", lambda job_id: dict(store["job"]))

    import app.services.cloud_run_launcher as launcher

    def _launch(job_id):
        store["launched"].append(job_id)
        return "operations/1"

    monkeypatch.setattr(launcher, "launch", _launch)
    client = TestClient(dispatcher.create_dispatcher_app())
    with client:
        yield client, store


def test_dispatcher_rejects_bad_secret(dispatcher_client):
    client, _ = dispatcher_client
    resp = client.post("/dispatch/j", headers={"X-Dispatch-Secret": "wrong"})
    assert resp.status_code == 403


def test_dispatcher_launches_queued_once(dispatcher_client):
    client, store = dispatcher_client
    headers = {"X-Dispatch-Secret": "secret"}
    first = client.post("/dispatch/j", headers=headers)
    assert first.json()["launched"] == "operations/1"
    store["job"]["status"] = "processing"
    second = client.post("/dispatch/j", headers=headers)
    assert second.json()["duplicate"] is True
    assert store["launched"] == ["j"]


def test_dispatcher_failed_launch_retries(dispatcher_client, monkeypatch):
    import app.services.cloud_run_launcher as launcher

    client, _ = dispatcher_client

    def _fail(job_id):
        raise ConnectionError("denied")

    monkeypatch.setattr(launcher, "launch", _fail)
    resp = client.post("/dispatch/j", headers={"X-Dispatch-Secret": "secret"})
    assert resp.status_code == 502


# --- Groq transcription ------------------------------------------------------

def test_groq_transcription_in_cloud(monkeypatch):
    import httpx as httpx_module
    from app.services import audio

    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "groq_api_key", "groq-test")
    monkeypatch.setattr(cfg, "groq_whisper_model", "whisper-large-v3-turbo")
    seen = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, files=None, data=None):
            seen.update(url=url, headers=headers, files=files, data=data)

            class _Resp:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"text": "hello world"}

            return _Resp()

    monkeypatch.setattr(httpx_module, "Client", _FakeClient)
    out = audio.transcribe(b"ID3" + b"\x00" * 100, "note.mp3")
    assert out == {"title": "note", "text": "hello world"}
    assert seen["url"].endswith("/audio/transcriptions")
    assert seen["headers"]["Authorization"] == "Bearer groq-test"
    assert seen["data"]["model"] == "whisper-large-v3-turbo"


def test_groq_transcription_size_cap(monkeypatch):
    from app.services import audio

    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "groq_api_key", "groq-test")
    with pytest.raises(ValueError):
        audio.transcribe(b"\x00" * (25 * 1024 * 1024 + 1), "big.mp3")


# --- spool uploads ------------------------------------------------------------

@pytest.mark.anyio
async def test_spool_upload_roundtrip_and_cleanup():
    import os

    from fastapi import UploadFile

    from app.core.uploads import discard_spooled, spool_upload

    import io

    upload = UploadFile(filename="doc.pdf", file=io.BytesIO(b""))
    chunks = [b"a" * 100, b"b" * 100]
    it = iter(chunks + [b""])

    async def _read(n):
        return next(it)

    upload.read = _read  # type: ignore[method-assign]
    path, size = await spool_upload(upload)
    try:
        assert size == 200
        with open(path, "rb") as handle:
            assert handle.read() == b"a" * 100 + b"b" * 100
    finally:
        discard_spooled(path)
    assert not os.path.exists(path)


@pytest.mark.anyio
async def test_spool_upload_rejects_oversize():
    from fastapi import UploadFile

    from app.core.uploads import spool_upload

    import io

    upload = UploadFile(filename="big.pdf", file=io.BytesIO(b""))

    async def _read(n):
        return b"x" * 1024

    upload.read = _read  # type: ignore[method-assign]
    with pytest.raises(Exception):
        await spool_upload(upload, max_size=100)


# --- single-job worker entrypoint ----------------------------------------------

def test_gcp_worker_requires_job_id(monkeypatch):
    import os

    from app import gcp_worker

    cfg = get_settings()
    monkeypatch.setattr(cfg, "mindmesh_execution_mode", "cloud")
    monkeypatch.setattr(cfg, "job_backend", "gcp")
    monkeypatch.delenv("MINDMESH_JOB_ID", raising=False)
    with pytest.raises(RuntimeError):
        gcp_worker.main()
    assert os.environ.get("MINDMESH_JOB_ID", "") == ""
