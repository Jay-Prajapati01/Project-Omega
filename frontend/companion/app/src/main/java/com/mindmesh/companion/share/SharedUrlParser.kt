package com.mindmesh.companion.share

import android.content.ClipData
import android.content.Intent

/**
 * Pulls the shared URL out of an Android share intent.
 *
 * Share sheets are inconsistent: Instagram and YouTube sometimes send the link
 * as `EXTRA_TEXT`, sometimes only as `EXTRA_SUBJECT`, sometimes as an intent
 * data URI, and sometimes as clip-data items. Every one of those is inspected,
 * and scheme-less links ("instagram.com/reel/…") are normalised to https so the
 * field is never silently empty.
 */
object SharedUrlParser {
    private val URL_REGEX = Regex("""https?://[^\s<>"'{}|\\^`\[\]]+""", RegexOption.IGNORE_CASE)
    private val BARE_REGEX = Regex("""(?<![@\w./])(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+(?::\d{2,5})?/[^\s<>"'{}|\\^`\[\]]*""", RegexOption.IGNORE_CASE)
    private val TRAILING_PUNCTUATION = charArrayOf('.', ',', ';', '!', '?', '"', '\'', ')', ']', '}')
    private val BLOCKED_HOSTS = setOf("localhost", "127.0.0.1", "0.0.0.0")
    private val ALLOWED_HOSTS = setOf("youtube.com", "youtu.be", "instagram.com")

    /** First usable https link found in the intent, or null when none arrived. */
    fun from(intent: Intent?): String? = candidates(intent).firstNotNullOfOrNull { extract(it) }

    /** Every string the intent could plausibly carry, in priority order. */
    fun candidates(intent: Intent?): List<String> {
        if (intent == null) return emptyList()
        if (intent.action != Intent.ACTION_SEND && intent.action != Intent.ACTION_VIEW) return emptyList()
        val values = mutableListOf<String>()
        extraText(intent, Intent.EXTRA_TEXT)?.let(values::add)
        extraText(intent, Intent.EXTRA_SUBJECT)?.let(values::add)
        intent.dataString?.takeIf { it.isNotBlank() }?.let(values::add)
        intent.clipData?.let { clip -> collectClip(clip, values) }
        return values
    }

    /** EXTRA_TEXT may arrive as String or CharSequence depending on the sender. */
    private fun extraText(intent: Intent, key: String): String? =
        runCatching { intent.extras?.get(key) }.getOrNull()
            ?.toString()
            ?.takeIf { it.isNotBlank() }

    private fun collectClip(clip: ClipData, values: MutableList<String>) {
        for (index in 0 until minOf(clip.itemCount, 4)) {
            val item = clip.getItemAt(index)
            item.text?.toString()?.takeIf { it.isNotBlank() }?.let(values::add)
            item.uri?.toString()?.takeIf { it.isNotBlank() }?.let(values::add)
        }
    }

    /** Extracts and normalises the first https URL inside free-form share text. */
    fun extract(text: String?): String? {
        if (text.isNullOrBlank()) return null
        URL_REGEX.find(text)?.let { match -> return sanitise(match.value) }
        BARE_REGEX.find(text)?.let { match -> return sanitise("https://${match.value}") }
        return null
    }

    private fun sanitise(raw: String): String? {
        var url = raw.trim()
        while (url.isNotEmpty() && url.last() in TRAILING_PUNCTUATION) url = url.dropLast(1)
        if (url.isEmpty()) return null
        val parsed = runCatching { java.net.URI(url) }.getOrNull() ?: return null
        val scheme = parsed.scheme?.lowercase()
        if (scheme != "https" && scheme != "http") return null
        val host = parsed.host?.lowercase() ?: return null
        if (host.isBlank() || host in BLOCKED_HOSTS || !host.contains('.')) return null
        if (!host.substringAfterLast('.').all { it.isLetter() }) return null
        if (ALLOWED_HOSTS.none { host == it || host.endsWith(".$it") }) return null
        return url
    }
}
