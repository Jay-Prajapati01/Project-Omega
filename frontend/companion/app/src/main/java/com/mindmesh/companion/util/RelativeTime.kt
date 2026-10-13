package com.mindmesh.companion.util

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Small, locale-stable relative timestamps for the recent-saves list. */
object RelativeTime {
    private const val MINUTE = 60_000L
    private const val HOUR = 60 * MINUTE
    private const val DAY = 24 * HOUR

    fun format(now: Long, then: Long): String {
        val delta = now - then
        return when {
            delta < 0L -> "just now"
            delta < MINUTE -> "just now"
            delta < HOUR -> "${delta / MINUTE}m ago"
            delta < DAY -> "${delta / HOUR}h ago"
            delta < 7 * DAY -> "${delta / DAY}d ago"
            else -> SimpleDateFormat("d MMM yyyy", Locale.US).format(Date(then))
        }
    }
}
