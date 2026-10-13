"""Upload helpers: bounded reads so an oversized file never lands fully in memory.

Two intake shapes:
* read_upload — bounded in-memory read for the local development paths.
* spool_upload — bounded disk spool for cloud mode: bytes stream straight
  to a temp file (Cloud Run ephemeral disk) so a large upload is never held
  twice in the API container's heap, and the outbound storage PUT streams
  from disk (see cloud_storage.put_file).
"""
from __future__ import annotations

import os
import tempfile

from fastapi import HTTPException, UploadFile

from app.core.config import get_settings

_CHUNK = 1024 * 1024  # 1 MB


def _too_large(limit: int) -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"File exceeds the {limit // (1024 * 1024)} MB upload limit",
    )


async def read_upload(file: UploadFile, max_size: int | None = None) -> bytes:
    """Read an upload fully, rejecting it once it exceeds max_size bytes.

    Defaults to Settings.max_upload_size. Raises 413 when over the limit.
    """
    limit = max_size if max_size is not None else get_settings().max_upload_size
    if file.size is not None and file.size > limit:
        raise _too_large(limit)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise _too_large(limit)
        chunks.append(chunk)
    return b"".join(chunks)


async def spool_upload(file: UploadFile, max_size: int | None = None) -> tuple[str, int]:
    """Stream an upload to a temp file. Returns (temp_path, size_bytes).

    The caller owns the temp file and must remove it (see discard_spooled).
    Raises 413 once the stream exceeds max_size bytes.
    """
    limit = max_size if max_size is not None else get_settings().max_upload_size
    if file.size is not None and file.size > limit:
        raise _too_large(limit)
    fd, path = tempfile.mkstemp(prefix="mindmesh-upload-", suffix=".bin")
    total = 0
    try:
        with os.fdopen(fd, "wb") as tmp:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise _too_large(limit)
                tmp.write(chunk)
    except BaseException:
        discard_spooled(path)
        raise
    return path, total


def discard_spooled(path: str) -> None:
    """Best-effort removal of a spooled temp file."""
    try:
        os.unlink(path)
    except OSError:
        pass
