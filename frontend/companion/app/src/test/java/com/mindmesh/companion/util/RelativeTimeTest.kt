package com.mindmesh.companion.util

import org.junit.Assert.assertEquals
import org.junit.Test

class RelativeTimeTest {
    private val now = 1_760_000_000_000L

    @Test
    fun `seconds and future timestamps read as just now`() {
        assertEquals("just now", RelativeTime.format(now, now - 5_000L))
        assertEquals("just now", RelativeTime.format(now, now - 59_000L))
        assertEquals("just now", RelativeTime.format(now, now + 60_000L))
    }

    @Test
    fun `minutes and hours`() {
        assertEquals("5m ago", RelativeTime.format(now, now - 5 * 60_000L))
        assertEquals("59m ago", RelativeTime.format(now, now - 59 * 60_000L))
        assertEquals("3h ago", RelativeTime.format(now, now - 3 * 60 * 60_000L))
    }

    @Test
    fun `days then an absolute date`() {
        assertEquals("2d ago", RelativeTime.format(now, now - 2 * 24 * 60 * 60_000L))
        assertEquals("6d ago", RelativeTime.format(now, now - 6 * 24 * 60 * 60_000L))
        assertEquals("2 Oct 2025", RelativeTime.format(now, now - 7 * 24 * 60 * 60_000L))
        assertEquals("9 Sep 2025", RelativeTime.format(now, now - 30 * 24 * 60 * 60_000L))
    }
}
