"""Magic-byte validation for uploaded files.

Extension checks alone accept polyglots and mislabeled binaries. Every
upload is sniffed against the declared extension before it is staged or
parsed; mismatches are rejected before any expensive processing runs.
"""
from __future__ import annotations

import zipfile
from pathlib import PurePath

# Extension -> predicate over the first bytes of the file.
_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv"}


def _is_zip(data: bytes) -> bool:
    return data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def _is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _is_mp3(data: bytes) -> bool:
    return data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)


def _is_wav(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def _is_flac(data: bytes) -> bool:
    return data[:4] == b"fLaC"


def _is_ogg(data: bytes) -> bool:
    return data[:4] == b"OggS"


def _is_webm(data: bytes) -> bool:
    return data[:4] == b"\x1a\x45\xdf\xa3"


def _is_mp4(data: bytes) -> bool:
    return len(data) > 12 and data[4:8] == b"ftyp"


def _is_aac(data: bytes) -> bool:
    return len(data) > 1 and data[0] == 0xFF and (data[1] & 0xF6) in (0xF0, 0xF8)


def _looks_textual(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:4096]
    if b"\x00" in sample:
        return False
    # Reject control characters other than common whitespace.
    control = sum(1 for b in sample if b < 9 or (13 < b < 32))
    return control / max(len(sample), 1) < 0.05


_VALIDATORS = {
    ".pdf": _is_pdf,
    ".docx": _is_zip,
    ".pptx": _is_zip,
    ".xlsx": _is_zip,
    ".mp3": _is_mp3,
    ".wav": _is_wav,
    ".flac": _is_flac,
    ".ogg": _is_ogg,
    ".webm": _is_webm,
    ".m4a": _is_mp4,
    ".mp4": _is_mp4,
    ".aac": _is_aac,
}


class FileSignatureError(ValueError):
    """File content does not match its extension."""


def validate_signature(filename: str, data: bytes) -> None:
    """Raise FileSignatureError when *data* does not match *filename*'s type."""
    suffix = PurePath(filename.replace("\\", "/")).suffix.lower()
    if not data:
        raise FileSignatureError("Empty file")
    if suffix in _TEXT_SUFFIXES:
        if not _looks_textual(data):
            raise FileSignatureError("File content is not valid text for this extension")
        return
    validator = _VALIDATORS.get(suffix)
    if validator is None:
        # Unknown extension: never reached for allowlisted staging paths,
        # but keep a safe default — require the payload to be text.
        if not _looks_textual(data):
            raise FileSignatureError("Unsupported binary file format")
        return
    if not validator(data):
        raise FileSignatureError("File content does not match its extension")

    # Office formats must additionally be readable as zip containers so a
    # zip bomb / corrupt archive is caught before the parser runs.
    if suffix in {".docx", ".pptx", ".xlsx"}:
        try:
            with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
                bad = zf.testzip()
                if bad is not None:
                    raise FileSignatureError("Corrupt archive member: " + bad)
        except zipfile.BadZipFile as exc:
            raise FileSignatureError("Corrupt or non-zip Office document") from exc
