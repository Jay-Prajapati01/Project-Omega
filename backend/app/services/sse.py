"""Server-Sent Events (SSE) helpers for streaming progress from FastAPI."""
from __future__ import annotations

import json


def sse(event: str, data: dict | str) -> str:
    """Format a single SSE message ready to be yielded."""
    if isinstance(data, dict):
        data = json.dumps(data, default=str)
    return f"event: {event}\ndata: {data}\n\n"


def public_error(exc: BaseException, context: str = "Processing") -> str:
    """Client-safe error text for `step_fail` events.

    Domain ValueErrors carry our own code-controlled messages (validation,
    SSRF blocks) and are shown verbatim. Everything else is reduced to the
    exception type so internal URLs, filesystem paths and library internals
    cannot leak over the stream — details go to the server log instead.
    """
    if isinstance(exc, ValueError):
        return str(exc)
    return (
        f"{context} failed ({type(exc).__name__}). "
        "Details are in the server logs."
    )
