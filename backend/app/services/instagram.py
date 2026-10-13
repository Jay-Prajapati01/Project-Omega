"""Instagram ingestion: captions + OCR of media + audio transcription.

Uses Playwright to render Instagram pages and extract content from public
posts/reels without requiring login. Falls back to instaloader if login
credentials are provided.

Video audio is transcribed with Faster-Whisper; image frames are OCR'd
with pytesseract. All extracted text is combined into a single document
for the shared ingestion pipeline.
"""
from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_SHORTCODE_RE = re.compile(r"instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")


def extract_shortcode(url: str) -> str:
    """Extract the Instagram shortcode from a post/reel URL."""
    match = _SHORTCODE_RE.search(url)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]+", url):
        return url
    raise ValueError(f"Could not extract an Instagram shortcode from: {url}")


def _ocr_image(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(path)).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR failed for %s: %s", path, exc)
        return ""


def _transcribe_audio(path: Path) -> str:
    try:
        from app.services.whisper_model import get_model

        model = get_model()
        segments, _ = model.transcribe(str(path))
        return " ".join(seg.text for seg in segments).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audio transcription failed for %s: %s", path, exc)
        return ""


def _extract_data_from_page(html: str, body_text: str, shortcode: str) -> dict | None:
    """Extract Instagram post data from rendered page HTML and text."""
    username = ""
    caption = ""
    thumbnail = ""

    # Extract username from various patterns
    username_patterns = [
        r'"username":\s*"([^"]+)"',
        r'href="https://www\.instagram\.com/([^/"]+)/\?',
        r'class="[^"]*Username[^"]*"[^>]*>([^<]+)',
    ]
    for pattern in username_patterns:
        match = re.search(pattern, html)
        if match:
            username = match.group(1).strip()
            if username and len(username) > 2 and username not in ("instagram", "login", "signup"):
                break
            username = ""

    # Extract caption from body text
    # The body text has structure: "username\n•\ntimestamp\ncaption\ncomments..."
    lines = body_text.strip().split("\n")
    caption_lines = []
    in_caption = False
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        # Skip navigation/UI elements
        if line in ("Log In", "Sign Up", "Log in", "Sign up", "Follow", "Meta",
                     "About", "Blog", "Jobs", "Help", "API", "Privacy", "Terms",
                     "Locations", "Popular", "Instagram Lite", "Meta AI", "Threads",
                     "Contact Uploading & Non-User"):
            continue
        if line.startswith("Never miss a post"):
            continue
        if line.startswith("Sign up for Instagram"):
            continue
        if line.startswith("By continuing"):
            continue
        # Skip comment-related patterns
        if re.match(r"^\d+[smhd]$", line):  # timestamps like "6h", "32s"
            in_caption = True
            continue
        if re.match(r"^\d+(\.\d+)?[KkMm]$", line):  # like/comment counts
            continue
        if line in ("Like", "Reply", "More posts from"):
            in_caption = False
            continue
        if line.startswith("See more posts"):
            in_caption = False
            continue
        if line.startswith("Log in to like"):
            in_caption = False
            continue
        # Check for username line (followed by timestamp)
        if i + 1 < len(lines) and lines[i + 1].strip() == "•":
            in_caption = True
            continue
        if in_caption and len(line) > 3:
            caption_lines.append(line)

    if caption_lines:
        caption = " ".join(caption_lines)

    # Extract thumbnail from HTML
    cdn_match = re.search(r'(https://scontent[^"\']+)', html)
    if cdn_match:
        thumbnail = cdn_match.group(1).replace("&amp;", "&")

    # Extract like/comment counts from body text
    stats = {}
    for line in lines:
        line = line.strip()
        if re.match(r"^\d+(\.\d+)?[KkMm]$", line):
            if "likes" not in stats:
                stats["likes"] = line
            elif "comments" not in stats:
                stats["comments"] = line

    text_parts = []
    if caption:
        text_parts.append(f"Caption: {caption}")

    # Add comments from body text
    comments = []
    in_comments = False
    for line in lines:
        line = line.strip()
        if line == "Log in to like or comment.":
            in_comments = False
            continue
        if "More posts from" in line:
            in_comments = False
            continue
        if in_comments and line and line not in ("Like", "Reply"):
            if not re.match(r"^\d+(\.\d+)?[KkMm]$", line):
                comments.append(line)

    if comments:
        text_parts.append("Comments:\n" + "\n".join(comments[:20]))

    text = "\n\n".join(text_parts).strip()
    title = (caption[:80] + "...") if len(caption) > 80 else (caption or shortcode)

    if not text:
        return None

    return {
        "shortcode": shortcode,
        "title": title,
        "caption": caption,
        "text": text,
        "thumbnail": thumbnail,
        "owner": username,
    }


def _fetch_via_playwright(shortcode: str, original_url: str) -> dict | None:
    """Fetch Instagram post data using Playwright headless browser."""

    # Determine the URL type
    if "/reel/" in original_url or "/reels/" in original_url:
        page_url = f"https://www.instagram.com/reel/{shortcode}/"
    else:
        page_url = f"https://www.instagram.com/p/{shortcode}/"

    async def _scrape():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            from app.core.browser_guard import protect_context
            await protect_context(context)
            page = await context.new_page()

            try:
                await page.goto(page_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                html = await page.content()
                body_text = await page.inner_text("body")

                await browser.close()
                return html, body_text
            except Exception as exc:
                logger.warning("Playwright navigation failed for %s: %s", shortcode, exc)
                await browser.close()
                return None, None

    try:
        # Run async Playwright in a thread to avoid event loop conflict with FastAPI
        import concurrent.futures

        def _run_playwright():
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_scrape())
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            html, body_text = pool.submit(_run_playwright).result(timeout=60)
    except Exception as exc:
        logger.warning("Playwright scrape failed for %s: %s", shortcode, exc)
        return None

    if not html or not body_text:
        return None

    return _extract_data_from_page(html, body_text, shortcode)


def _fetch_via_instaloader(shortcode: str) -> dict | None:
    """Try fetching via instaloader (requires login credentials)."""
    from app.core.config import get_settings

    settings = get_settings()
    ig_user = settings.ig_username
    ig_pass = settings.ig_password

    if not ig_user or not ig_pass:
        return None

    import instaloader

    loader = instaloader.Instaloader(
        download_comments=False,
        save_metadata=False,
        quiet=True,
    )

    # Try session file first
    session_file = Path("/app/data/instagram-sessionfile")
    if session_file.exists():
        try:
            loader.load_session_from_file(ig_user, str(session_file))
            logger.info("Loaded Instagram session from file for %s", ig_user)
        except Exception as exc:
            logger.warning("Session file load failed: %s", exc)

    try:
        loader.login(ig_user, ig_pass)
        logger.info("Logged in to Instagram as %s", ig_user)
        # Save session for future use
        try:
            session_file.parent.mkdir(parents=True, exist_ok=True)
            loader.save_session_to_file(str(session_file))
        except Exception:
            pass
    except Exception as exc:
        logger.warning("Instagram login failed for %s: %s", ig_user, exc)
        return None

    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        caption = post.caption or ""
        owner = post.owner_username
        thumbnail = post.url

        parts: list[str] = []
        if caption:
            parts.append(f"Caption: {caption}")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / shortcode
            target.mkdir(parents=True, exist_ok=True)
            try:
                loader.download_post(post, target=str(target))
            except Exception as exc:
                logger.warning("Media download failed for %s: %s", shortcode, exc)

            for img in list(target.glob("*.jpg")) + list(target.glob("*.png")):
                ocr = _ocr_image(img)
                if ocr:
                    parts.append(f"On-screen text: {ocr}")
            for vid in target.glob("*.mp4"):
                transcript = _transcribe_audio(vid)
                if transcript:
                    parts.append(f"Spoken: {transcript}")

        text = "\n\n".join(parts).strip()
        title = (caption[:80] + "...") if len(caption) > 80 else (caption or shortcode)
        return {
            "shortcode": shortcode,
            "title": title,
            "caption": caption,
            "text": text,
            "thumbnail": thumbnail,
            "owner": owner,
        }
    except Exception as exc:
        logger.warning("instaloader failed for %s: %s", shortcode, exc)
        return None


def fetch_post(url: str) -> dict:
    """Fetch an Instagram post/reel: caption, OCR text, and transcript.

    Tries multiple strategies:
    1. Playwright headless browser (works for public posts, no login needed)
    2. instaloader (requires IG_USERNAME/IG_PASSWORD)

    Returns a dict with keys: shortcode, title, caption, text, thumbnail, owner.
    """
    shortcode = extract_shortcode(url)

    # Strategy 1: Playwright (works for public posts)
    result = _fetch_via_playwright(shortcode, url)
    if result and result["text"]:
        logger.info("Fetched Instagram post %s via Playwright", shortcode)
        return result

    # Strategy 2: instaloader (requires login)
    result = _fetch_via_instaloader(shortcode)
    if result and result["text"]:
        logger.info("Fetched Instagram post %s via instaloader", shortcode)
        return result

    raise ValueError(
        f"Could not fetch Instagram post {shortcode}. "
        "The post may be private, or Instagram may be blocking automated access. "
        "Try setting IG_USERNAME and IG_PASSWORD in backend/.env for authenticated access."
    )
