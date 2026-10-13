"""Only trusted server processes call Modal. No local fallback in cloud mode."""
from app.core.config import get_settings
from app.core.tenant import scope


class WorkerUnavailable(RuntimeError):
    """Sanitized retryable remote inference failure."""


def model(name: str):
    import modal
    cfg = get_settings()
    return modal.Cls.from_name(cfg.modal_app_name, name, environment_name=cfg.modal_environment)()


async def generate(prompt: str, system: str | None = None) -> str:
    envelope = scope().envelope()
    try:
        return await model("Qwen").generate.remote.aio(envelope, prompt, system)
    except Exception as exc:
        raise WorkerUnavailable("Inference unavailable") from exc


async def embed(texts: list[str]) -> list[list[float]]:
    envelope = scope().envelope()
    try:
        return await model("Embeddings").embed.remote.aio(envelope, texts)
    except Exception as exc:
        raise WorkerUnavailable("Embeddings unavailable") from exc


def transcribe(path: str) -> list[dict]:
    # Stage private audio in cloud storage instead of shipping Windows paths to Modal.
    import uuid
    from pathlib import Path
    from app.services import cloud_storage
    owner = scope()
    relative = f"scratch/{owner.job_id}/{uuid.uuid4()}{Path(path).suffix}"
    cloud_storage.put(relative, Path(path).read_bytes())
    try:
        return model("Whisper").transcribe.remote(owner.envelope(), relative)
    except Exception as exc:
        raise WorkerUnavailable("Transcription unavailable") from exc
    finally:
        cloud_storage.delete(relative)
