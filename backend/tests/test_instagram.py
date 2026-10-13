"""Tests for Instagram shortcode extraction."""
import pytest

from app.services.instagram import extract_shortcode


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.instagram.com/reel/CabcDEF123/", "CabcDEF123"),
        ("https://instagram.com/p/CabcDEF123/", "CabcDEF123"),
        ("CabcDEF123", "CabcDEF123"),
    ],
)
def test_extract_shortcode(url, expected):
    assert extract_shortcode(url) == expected


def test_invalid_raises():
    with pytest.raises(ValueError):
        extract_shortcode("https://example.com/not-instagram")
