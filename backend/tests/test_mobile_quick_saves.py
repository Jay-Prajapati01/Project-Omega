from app.api.mobile import _kind


def test_quick_save_classifies_supported_sources():
    assert _kind("https://youtu.be/dQw4w9WgXcQ") == "videos"
    assert _kind("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "videos"
    assert _kind("https://www.instagram.com/reel/ABC_12/") == "instagram"
    assert _kind("https://m.instagram.com/reel/ABC_12/") == "instagram"

    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        _kind("https://example.com/article")
    assert error.value.status_code == 422


def test_quick_save_rejects_non_urls():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _kind("not a url")
    assert error.value.status_code == 422
