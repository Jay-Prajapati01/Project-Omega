"""Structured application logging."""
import logging
import sys
import json

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    if settings.mindmesh_execution_mode in {"modal", "cloud"}:
        handler.setFormatter(CloudFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


class CloudFormatter(logging.Formatter):
    """Allowlisted JSON fields only; suppress legacy exceptions, URLs and content."""
    def format(self, record):
        from app.core.tenant import current_scope
        owner = current_scope.get()
        data = {"level": record.levelname, "logger": record.name}
        if owner:
            data.update(tenant_id=owner.tenant_id, user_id=owner.user_id,
                        job_id=owner.job_id, resource_id=owner.resource_id)
        try:
            if record.name != "app.services.job_runner":
                raise ValueError("Unstructured event")
            event = json.loads(record.getMessage())
            data.update({k: event[k] for k in ("worker", "operation", "status", "duration_ms", "error") if k in event})
        except (ValueError, TypeError):
            data["event"] = "service_event"
        return json.dumps(data)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def safe_log_str(value: str, max_len: int = 200) -> str:
    """Sanitize a string for safe logging: strip control characters and truncate."""
    if not value:
        return ""
    # Strip control characters (except tab, newline, carriage return)
    cleaned = "".join(ch if ch >= " " or ch in "\t\n\r" else "\\u{:04x}".format(ord(ch)) for ch in value)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "..."
    return cleaned
