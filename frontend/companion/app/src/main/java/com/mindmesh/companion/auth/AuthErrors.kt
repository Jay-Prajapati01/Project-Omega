package com.mindmesh.companion.auth

import java.io.IOException

/** Supabase answered, but with a non-2xx status. `status` is the HTTP code. */
class AuthHttpException(val status: Int, message: String, val detail: String? = null, val errorCode: String? = null) : Exception(message)

/** The device could not reach Supabase at all (offline, DNS, timeout, TLS). */
class AuthNetworkException(cause: Throwable) : Exception("Could not reach MindMesh. Check your connection.", cause)

/** Pure mapping from Supabase error payloads to messages a user can act on. */
object AuthErrors {
    private const val NOT_CONFIGURED = "Supabase is not configured for this build. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in android-companion/local.properties."

    fun notConfigured(): String = NOT_CONFIGURED

    fun friendly(status: Int, detail: String?, errorCode: String?, fallback: String): String {
        val text = detail.orEmpty().lowercase()
        val code = errorCode.orEmpty().lowercase()
        return when {
            status == 400 && (code.contains("invalid_credentials") || "invalid login" in text || "invalid" in text && "password" in text) ->
                "Email or password is incorrect."
            status == 400 && (code.contains("email_not_confirmed") || "not confirmed" in text || "confirm your email" in text) ->
                "Confirm your email first — the confirmation link is in your inbox."
            status == 400 && (code.contains("user_already_exists") || "already registered" in text || "already been registered" in text) ->
                "An account with this email already exists. Sign in instead."
            status == 400 && (code.contains("weak_password") || "password should be" in text) ->
                "Use a password with at least 8 characters."
            status == 400 && code.contains("validation_failed") ->
                detail ?: "Check the email address and password you entered."
            status == 400 && code.contains("user_not_found") ->
                "No MindMesh account exists for this email."
            status == 401 ->
                "Your session is no longer valid. Sign in again."
            status == 403 ->
                "This account is not allowed to use MindMesh."
            status == 404 ->
                "$fallback — the auth endpoint was not found. Check SUPABASE_URL."
            status == 429 || code.contains("over_request") || code.contains("over_email_send") ->
                "Too many attempts. Wait a minute and try again."
            status == 503 ->
                detail ?: "MindMesh authentication is temporarily unavailable."
            detail.isNullOrBlank() ->
                "$fallback (HTTP $status)."
            else ->
                "$fallback: $detail"
        }
    }

    fun isNetworkFailure(error: Throwable?): Boolean {
        var current = error
        var depth = 0
        while (current != null && depth < 8) {
            if (current is IOException) return true
            current = current.cause
            depth++
        }
        return false
    }
}
