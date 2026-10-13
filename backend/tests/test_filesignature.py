"""Magic-byte upload validation tests (audit P0-8; plan ING-002).

`validate_signature` is the last line of defence before a staged upload is
parsed: extension-only checks accept polyglots and mislabeled binaries, so
every case here pairs a plausible filename with hostile or mismatched bytes.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from app.core.filesignature import FileSignatureError, validate_signature


def _zip_bytes(payload: bytes = b"<w>hello</w>") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", payload)
    return buf.getvalue()


def _assert_ok(filename: str, data: bytes) -> None:
    assert validate_signature(filename, data) is None


def _assert_rejected(filename: str, data: bytes) -> None:
    with pytest.raises(FileSignatureError):
        validate_signature(filename, data)


# --- empty / hostile payloads -------------------------------------------------


def test_empty_file_rejected_everywhere():
    for name in ("a.pdf", "a.txt", "a.mp3"):
        _assert_rejected(name, b"")


def test_mislabeled_binary_as_pdf_rejected():
    # Windows executable renamed to .pdf (classic polyglot upload).
    _assert_rejected("report.pdf", b"MZ\x90\x00\x03\x00\x00\x00")
    _assert_ok("report.pdf", b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n")


def test_png_bytes_with_wrong_extension_rejected():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    _assert_rejected("photo.pdf", png)
    _assert_rejected("photo.docx", png)
    # .png is not an allowlisted staging extension: binary payloads behind
    # unknown extensions are rejected outright (text fallback only).
    _assert_rejected("photo.png", png)
    _assert_rejected("photo.xyz", png)


def test_pdf_bytes_dressed_as_audio_rejected():
    _assert_rejected("lecture.mp3", b"%PDF-1.4\n...")
    _assert_ok("lecture.mp3", b"ID3\x04\x00\x00\x00\x00\x00\x00rest")
    _assert_ok("lecture.mp3", b"\xff\xfb\x90\x00rest")  # MPEG frame sync


# --- text formats -------------------------------------------------------------


def test_text_formats_accept_plain_text():
    for name in ("notes.txt", "notes.md", "notes.markdown", "notes.csv"):
        _assert_ok(name, "id,title\n1,Hello\n".encode())


def test_text_extension_rejects_binary_content():
    _assert_rejected("notes.txt", b"PK\x03\x04\x00\x00binary\x00")
    _assert_rejected("notes.csv", b"\x00\x01\x02\x03" * 64)


def test_text_extension_rejects_control_character_soup():
    payload = bytes(range(32)) * 200  # dense C0 control characters
    _assert_rejected("notes.txt", payload)


# --- office containers --------------------------------------------------------


def test_valid_office_zip_accepted():
    data = _zip_bytes()
    _assert_ok("cv.docx", data)
    _assert_ok("deck.pptx", data)
    _assert_ok("sheet.xlsx", data)


def test_corrupt_office_zip_rejected():
    # Right magic bytes, broken archive: caught before python-docx runs.
    _assert_rejected("cv.docx", b"PK\x03\x04 this is not really a zip")


def test_zip_with_corrupt_member_rejected():
    payload = b"A" * 4096
    buf = io.BytesIO()
    # ZIP_STORED so the payload sits verbatim in the archive: corrupting it
    # trips the CRC check instead of the deflate stream.
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("word/document.xml", payload)
    data = bytearray(buf.getvalue())
    offset = data.find(b"A" * 16)
    assert offset > 0
    data[offset] ^= 0xFF
    _assert_rejected("cv.docx", bytes(data))


# --- media formats ------------------------------------------------------------


def test_media_signatures():
    _assert_ok("a.wav", b"RIFF\x24\x00\x00\x00WAVEfmt ")
    _assert_rejected("a.wav", b"RIFF\x24\x00\x00\x00AVI LIST")
    _assert_ok("a.flac", b"fLaC\x00\x00\x00\x22" + b"\x00" * 8)
    _assert_ok("a.ogg", b"OggS\x00\x02" + b"\x00" * 8)
    _assert_ok("a.webm", b"\x1a\x45\xdf\xa3" + b"\x00" * 8)
    _assert_ok("a.mp4", b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00")
    _assert_ok("a.m4a", b"\x00\x00\x00\x20ftypM4A \x00\x00\x02\x00")
    _assert_ok("a.aac", b"\xff\xf1\x50\x80\x00\x1f\xfc")
    _assert_rejected("a.mp4", b"RIFF\x00\x00\x00\x00WAVE")
    _assert_rejected("a.webm", b"%PDF-1.4\n")


# --- filenames ----------------------------------------------------------------


def test_suffix_matching_is_case_insensitive_and_path_aware():
    _assert_ok("Reports/Final.PDF", b"%PDF-1.4\n")
    _assert_ok("C:\\uploads\\Final.PdF", b"%PDF-1.4\n")
    _assert_rejected("C:\\uploads\\Final.PDF", b"MZ\x90\x00")
    # Double extensions must resolve to the real final suffix.
    _assert_rejected("invoice.pdf.exe", b"MZ\x90\x00\x03")
    _assert_ok("invoice.pdf.exe", "plain text hiding behind a double name".encode())
