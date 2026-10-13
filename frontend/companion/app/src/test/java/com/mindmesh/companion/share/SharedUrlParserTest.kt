package com.mindmesh.companion.share

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SharedUrlParserTest {
    @Test
    fun `extracts a plain https link`() {
        assertEquals(
            "https://www.instagram.com/reel/abc123/",
            SharedUrlParser.extract("https://www.instagram.com/reel/abc123/"),
        )
    }

    @Test
    fun `finds a link inside share copy`() {
        assertEquals(
            "https://youtube.com/shorts/xyz",
            SharedUrlParser.extract("Watch this great short: https://youtube.com/shorts/xyz — amazing!"),
        )
    }

    @Test
    fun `normalises scheme-less links`() {
        assertEquals(
            "https://instagram.com/reel/abc",
            SharedUrlParser.extract("instagram.com/reel/abc"),
        )
    }

    @Test
    fun `strips trailing punctuation`() {
        assertEquals(
            "https://instagram.com/p/a",
            SharedUrlParser.extract("see https://instagram.com/p/a."),
        )
        assertEquals(
            "https://youtu.be/b",
            SharedUrlParser.extract("(https://youtu.be/b)"),
        )
    }

    @Test
    fun `keeps query strings intact`() {
        assertEquals(
            "https://www.youtube.com/watch?v=abc&t=10",
            SharedUrlParser.extract("https://www.youtube.com/watch?v=abc&t=10"),
        )
    }

    @Test
    fun `rejects links outside YouTube and Instagram`() {
        assertNull(SharedUrlParser.extract("https://example.com/article"))
        assertNull(SharedUrlParser.extract("https://youtube.com.evil.test/watch?v=x"))
    }

    @Test
    fun `rejects localhost and loopback`() {
        assertNull(SharedUrlParser.extract("http://localhost:8000/api/health"))
        assertNull(SharedUrlParser.extract("http://127.0.0.1:8000/api/health"))
    }

    @Test
    fun `rejects hostnames without a real tld`() {
        assertNull(SharedUrlParser.extract("http://intranet/docs"))
        assertNull(SharedUrlParser.extract("http://192.168.1.5/share"))
    }

    @Test
    fun `rejects a bare domain with no path`() {
        assertNull(SharedUrlParser.extract("instagram.com"))
    }

    @Test
    fun `rejects blank and link-free text`() {
        assertNull(SharedUrlParser.extract(null))
        assertNull(SharedUrlParser.extract(""))
        assertNull(SharedUrlParser.extract("   "))
        assertNull(SharedUrlParser.extract("Just a caption with no link at all"))
    }

    @Test
    fun `ignores email addresses when looking for bare links`() {
        assertNull(SharedUrlParser.extract("mail me at person@example.com please"))
    }

    @Test
    fun `null intent has no candidates`() {
        assertEquals(emptyList<String>(), SharedUrlParser.candidates(null))
        assertEquals(null, SharedUrlParser.from(null))
    }
}
