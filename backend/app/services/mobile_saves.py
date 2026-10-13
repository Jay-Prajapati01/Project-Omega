"""Durable local-development receipt store for companion quick saves."""
from __future__ import annotations

import asyncio
import importlib
import json
import time
import uuid
from pathlib import Path

from app.core.tenant import data_directory, scope
from app.services.job_runner import HANDLERS

_tasks: dict[str, asyncio.Task] = {}
PROCESS_TIMEOUT_SECONDS = 180


def _path() -> Path:
    path = data_directory() / "mobile-quick-saves.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load() -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _write(rows: list[dict]) -> None:
    path = _path()
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(rows))
    temp.replace(path)


def create(kind: str, url: str, idempotency: str) -> tuple[dict, bool]:
    """Create a receipt and report whether this request is new.

    A companion retry may repeat the same idempotency key.  The caller uses
    the boolean to avoid charging the user's plan a second time for that same
    save.
    """
    owner = scope()
    job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{owner.user_id}:{idempotency}"))
    rows = _load()
    existing = next((row for row in rows if row["job_id"] == job_id), None)
    if existing:
        return existing, False
    row = {"job_id": job_id, "kind": kind, "url": url, "status": "queued", "result": None, "error": None,
           "updated_at": time.time()}
    rows.append(row)
    _write(rows)
    return row, True


def remove(job_id: str) -> None:
    """Remove a newly-created receipt when admission (for example quota) fails."""
    rows = _load()
    remaining = [row for row in rows if row["job_id"] != job_id]
    if len(remaining) != len(rows):
        _write(remaining)


def owned(job_id: str) -> dict:
    row = next((item for item in _load() if item["job_id"] == job_id), None)
    if not row:
        raise KeyError(job_id)
    return row


def update(job_id: str, **changes) -> dict:
    rows = _load()
    for row in rows:
        if row["job_id"] == job_id:
            row.update(changes, updated_at=time.time())
            _write(rows)
            return row
    raise KeyError(job_id)


async def run(job_id: str) -> None:
    record = owned(job_id)
    update(job_id, status="processing")
    try:
        module, handler, schema = HANDLERS[record["kind"]]
        api = importlib.import_module("app.api." + module)
        # Local tasks used to be kept only in memory. A container restart
        # could lose that task and leave the durable receipt on "processing"
        # forever. A deadline also gives a stuck provider a terminal outcome.
        result = await asyncio.wait_for(
            getattr(api, handler)(getattr(api, schema)(url=record["url"])),
            timeout=PROCESS_TIMEOUT_SECONDS,
        )
        update(job_id, status="completed", result=result.model_dump(mode="json"))
    except asyncio.TimeoutError:
        update(job_id, status="failed", error={"message": "Processing timed out. Retry this save from the companion app."})
    except Exception:  # public message avoids leaking internal provider details
        update(job_id, status="failed", error={"message": "Unable to process this save. Retry it from the companion app."})


def recover_orphaned(job_id: str) -> dict:
    """Requeue a receipt left in progress by a local API restart.

    The live task map is process-local. If it has no active task for a stored
    processing receipt, no work is running and it is safe to queue it again.
    """
    record = owned(job_id)
    task = _tasks.get(job_id)
    if record.get("status") == "processing" and (task is None or task.done()):
        record = update(job_id, status="queued", error=None)
    return record


def schedule(job_id: str) -> None:
    if job_id in _tasks and not _tasks[job_id].done():
        return
    task = asyncio.create_task(run(job_id))
    _tasks[job_id] = task
    task.add_done_callback(lambda _: _tasks.pop(job_id, None))
