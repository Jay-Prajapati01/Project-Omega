"""YouTube ingestion: metadata + transcript with Whisper fallback."""
from __future__ import annotations

import re

from app.core.logging import get_logger
from app.models.schemas import VideoMetadata

logger = get_logger(__name__)

_YT_ID_RE = re.compile(
    r"(?:v=|/shorts/|youtu\.be/|/embed/)([0-9A-Za-z_-]{11})"
)
_YT_HOST_RE = re.compile(r"(?:youtube\.com|youtu\.be)", re.IGNORECASE)
_PLAYLIST_RE = re.compile(r"(?:youtube\.com/playlist|[?&]list=[0-9A-Za-z_-]{6,})", re.IGNORECASE)
_CHANNEL_RE = re.compile(r"youtube\.com/(?:@|channel/|c/|user/)", re.IGNORECASE)
_VIDEO_ID_ONLY_RE = re.compile(r"[0-9A-Za-z_-]{11}")


def extract_video_id(url: str) -> str:
    """Extract the 11-char YouTube video id from a URL or raw id.

    Playlist and channel URLs are rejected with a specific message so the
    user isn't handed a generic "could not extract" error.
    """
    match = _YT_ID_RE.search(url)
    if match:
        # A watch URL with both v= and list= is still a single video — video wins.
        return match.group(1)
    if _VIDEO_ID_ONLY_RE.fullmatch(url):
        return url
    if _YT_HOST_RE.search(url):
        if _CHANNEL_RE.search(url):
            raise ValueError(
                "That is a YouTube channel URL. Open a specific video and paste "
                "its link (https://www.youtube.com/watch?v=...)."
            )
        if _PLAYLIST_RE.search(url):
            raise ValueError(
                "That is a YouTube playlist URL. Paste a single video link from "
                "the playlist instead (https://www.youtube.com/watch?v=...)."
            )
    raise ValueError(f"Could not extract a video id from: {url}")


def fetch_metadata(url: str) -> VideoMetadata:
    """Fetch video metadata using yt-dlp (no download)."""
    import yt_dlp

    video_id = extract_video_id(url)
    opts = {"quiet": True, "skip_download": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
        except Exception:
            logger.warning("yt_dlp metadata fetch failed for %s, falling back to oEmbed", video_id)
            # lightweight fallback to oEmbed (title, author, thumbnail)
            try:
                import httpx

                oembed_url = (
                    f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                )
                resp = httpx.get(oembed_url, timeout=10.0)
                resp.raise_for_status()
                data = resp.json()
                info = {
                    "title": data.get("title"),
                    "uploader": data.get("author_name"),
                    "thumbnail": data.get("thumbnail_url"),
                }
            except Exception:
                # Re-raise original error if fallback also fails
                raise
    return VideoMetadata(
        video_id=video_id,
        title=info.get("title"),
        channel=info.get("uploader") or info.get("channel"),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        published_at=info.get("upload_date"),
    )


def fetch_transcript(video_id: str) -> str:
    """Fetch transcript via the transcript API, else fall back to Whisper."""
    try:
        text = _transcript_api_fetch(video_id)
        if text:
            logger.info("Transcript fetched via API for %s", video_id)
            return text
        raise RuntimeError("transcript was empty")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Transcript API failed for %s: %s", video_id, exc)

    try:
        return _whisper_transcribe(video_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Whisper transcription also failed for %s: %s", video_id, exc)
        raise ValueError(
            f"Could not retrieve transcript for video {video_id}. "
            "The video may not have captions and audio download failed."
        ) from exc


def _transcript_api_fetch(video_id: str) -> str:
    """Fetch a transcript in whichever language the video actually has.

    `YouTubeTranscriptApi.fetch()` defaults to `languages=["en"]`, which fails
    for videos published as `en-US`/`en-GB` or in another language entirely.
    List what exists, prefer English (manual captions first), then any language.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    ytt = YouTubeTranscriptApi()
    transcripts = list(ytt.list(video_id))
    if not transcripts:
        raise RuntimeError("no transcripts available for this video")

    def rank(t) -> tuple[int, int]:
        lang = (t.language_code or "").lower()
        is_english = lang == "en" or lang.startswith("en-")
        # English first, then manual captions over auto-generated ones.
        return (0 if is_english else 1, 1 if t.is_generated else 0)

    best = min(transcripts, key=rank)
    logger.info(
        "Using transcript language %r (generated=%s) for %s",
        best.language_code, best.is_generated, video_id,
    )
    fetched = ytt.fetch(video_id, languages=[best.language_code])
    return " ".join(snippet.text for snippet in fetched).strip()


# Tried in order: YouTube's default web stream URLs return HTTP 403 for
# server-side downloads, while the android/ios clients still serve them.
_WHISPER_PLAYER_CLIENTS = ("android", "ios", "mweb", "tv", "web_safari", None)


def _whisper_transcribe(video_id: str) -> str:
    """Download audio with yt-dlp and transcribe with faster-whisper."""


    from app.services.whisper_model import get_model

    logger.info("Falling back to Whisper for %s", video_id)
    url = f"https://www.youtube.com/watch?v={video_id}"
    base_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
        ],
    }

    audio_path = _download_audio(url, base_opts)
    try:
        model = get_model()
        segments, _ = model.transcribe(str(audio_path))
        return " ".join(seg.text for seg in segments).strip()
    finally:
        audio_path.unlink(missing_ok=True)


def _download_audio(url: str, base_opts: dict):
    """Try each YouTube player client until one yields the audio stream.

    Returns a path to the audio file (kept alive in its own temp file) —
    the caller is responsible for deleting it after transcription.
    """
    import shutil
    import tempfile
    from pathlib import Path

    import yt_dlp

    failures: list[str] = []
    for client in _WHISPER_PLAYER_CLIENTS:
        tmp = tempfile.mkdtemp(prefix="yt-audio-")
        try:
            opts = dict(base_opts)
            opts["outtmpl"] = str(Path(tmp) / "audio.%(ext)s")
            if client:
                opts["extractor_args"] = {"youtube": {"player_client": [client]}}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            files = sorted(Path(tmp).glob("audio.*"))
            if not files:
                raise RuntimeError("yt-dlp produced no audio file")
            chosen = next((f for f in files if f.suffix == ".mp3"), files[0])

            keeper = tempfile.NamedTemporaryFile(
                delete=False, suffix=chosen.suffix, prefix="mindmesh-audio-"
            )
            keeper.close()
            with open(chosen, "rb") as src, open(keeper.name, "wb") as dst:
                shutil.copyfileobj(src, dst)
            return Path(keeper.name)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{client or 'default'}: {exc}")
            logger.warning(
                "yt-dlp audio download failed (client=%s) for %s: %s",
                client or "default", url, exc,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    raise RuntimeError("All yt-dlp player clients failed -> " + "; ".join(failures))
