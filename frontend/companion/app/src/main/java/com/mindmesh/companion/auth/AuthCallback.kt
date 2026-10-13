package com.mindmesh.companion.auth

/** Clone-only native OAuth callback; it must return to this app, not the web workspace. */
object AuthCallback {
    const val URI = "mindmeshclone://auth/callback"

    fun matches(scheme: String?, host: String?, path: String?): Boolean =
        scheme == "mindmeshclone" && host == "auth" && path == "/callback"
}
