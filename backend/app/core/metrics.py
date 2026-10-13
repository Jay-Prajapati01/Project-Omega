"""In-process metrics registry with a Prometheus text exposition endpoint.

Counters are intentionally low-cardinality (status class, route class,
event name) so the endpoint can never grow unbounded or leak request data.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

_lock = threading.Lock()
_counters: dict[str, float] = defaultdict(float)
_gauges: dict[str, float] = {}
_started = time.time()


def inc(name: str, value: float = 1.0, **labels: str) -> None:
    key = _key(name, labels)
    with _lock:
        _counters[key] += value


def set_gauge(name: str, value: float, **labels: str) -> None:
    with _lock:
        _gauges[_key(name, labels)] = value


def _key(name: str, labels: dict[str, str]) -> str:
    if not labels:
        return name
    rendered = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{rendered}}}"


def snapshot() -> dict[str, float]:
    with _lock:
        return {**_counters, **_gauges}


def render() -> str:
    """Prometheus text format (0.0.4)."""
    lines = [
        "# HELP mindmesh_process_uptime_seconds Process uptime.",
        "# TYPE mindmesh_process_uptime_seconds gauge",
        f"mindmesh_process_uptime_seconds {time.time() - _started:.3f}",
    ]
    with _lock:
        items = sorted({**_counters, **_gauges}.items())
    seen_types: set[str] = set()
    for key, value in items:
        name = key.split("{", 1)[0]
        metric = f"mindmesh_{name}"
        if name not in seen_types:
            seen_types.add(name)
            lines.append(f"# TYPE {metric} gauge")
        lines.append(f"{metric} {value:g}")
    return "\n".join(lines) + "\n"


def reset() -> None:
    with _lock:
        _counters.clear()
        _gauges.clear()
