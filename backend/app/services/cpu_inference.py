"""CPU models for the private queue worker, never loaded inside the public API."""
import threading

from app.core.config import get_settings
from app.core.tenant import scope
from app.services.modal_client import WorkerUnavailable

_lock = threading.Lock()
_embedding = None
_speech = None


def authorize():
    if not get_settings().worker_process:
        raise WorkerUnavailable("Inference requires a queue worker")
    from app.services.job_runner import authorize as authorize_job
    authorize_job(scope().envelope())


def embed(texts: list[str]) -> list[list[float]]:
    authorize()
    if any(len(t) > 40000 for t in texts):
        raise ValueError("Embedding input exceeds limits")
    global _embedding
    with _lock:
        if _embedding is None:
            from sentence_transformers import SentenceTransformer
            _embedding = SentenceTransformer("BAAI/bge-m3", device="cpu")
            _embedding.max_seq_length = 8192
        return _embedding.encode(texts, batch_size=2, normalize_embeddings=True).tolist()


def whisper():
    authorize()
    global _speech
    with _lock:
        if _speech is None:
            from faster_whisper import WhisperModel
            _speech = WhisperModel("base", device="cpu", compute_type="int8")
    return _speech
