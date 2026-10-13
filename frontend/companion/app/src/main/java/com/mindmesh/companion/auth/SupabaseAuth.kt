package com.mindmesh.companion.auth

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Base64
import android.util.Log
import com.google.gson.Gson
import com.mindmesh.companion.BuildConfig
import java.io.IOException
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

data class SignedInUser(val id: String, val email: String?)
data class SignInSession(val accessToken: String, val refreshToken: String, val user: SignedInUser)

/** What a sign-up produced: a live session, or an email the user must confirm. */
sealed interface SignUpOutcome {
    data class SignedIn(val session: SignInSession) : SignUpOutcome
    data class ConfirmEmail(val email: String) : SignUpOutcome
}

/**
 * Uses Supabase's public auth API only. Service-role keys and provider secrets
 * are never embedded in the app. Every network call runs off the main thread and
 * surfaces typed failures so the UI can show actionable messages.
 */
object SupabaseAuth {
    private const val TAG = "MindMeshAuth"
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()
    private val gson = Gson()
    private val jsonType = "application/json".toMediaType()

    private fun configured(): Boolean =
        BuildConfig.SUPABASE_URL.isNotBlank() && BuildConfig.SUPABASE_PUBLISHABLE_KEY.isNotBlank()

    private fun requireConfigured() {
        check(configured()) { AuthErrors.notConfigured() }
    }

    private fun base(): String = BuildConfig.SUPABASE_URL.trimEnd('/')

    private fun post(path: String, payload: Map<String, Any?>, fallback: String): Map<*, *>? {
        requireConfigured()
        val request = Request.Builder()
            .url("${base()}$path")
            .header("apikey", BuildConfig.SUPABASE_PUBLISHABLE_KEY)
            .header("Content-Type", "application/json")
            .post(gson.toJson(payload).toRequestBody(jsonType))
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                val raw = response.body?.string()
                if (!response.isSuccessful) throw httpError(response.code, raw, fallback)
                @Suppress("UNCHECKED_CAST")
                if (raw.isNullOrBlank()) null
                else gson.fromJson(raw, Map::class.java) as? Map<*, *>
            }
        } catch (error: AuthHttpException) {
            throw error
        } catch (error: IOException) {
            Log.w(TAG, "network failure on $path", error)
            throw AuthNetworkException(error)
        }
    }

    private fun httpError(code: Int, raw: String?, fallback: String): AuthHttpException {
        var description: String? = null
        var errorCode: String? = null
        runCatching {
            @Suppress("UNCHECKED_CAST")
            val json = raw?.takeIf { it.isNotBlank() }?.let { gson.fromJson(it, Map::class.java) as? Map<*, *> }
            description = json?.get("error_description") as? String
                ?: json?.get("msg") as? String
                ?: json?.get("message") as? String
            errorCode = json?.get("error_code") as? String ?: json?.get("code") as? String
        }
        Log.w(TAG, "supabase $fallback failed: HTTP $code $raw")
        val message = AuthErrors.friendly(code, description, errorCode, fallback)
        return AuthHttpException(code, message, description, errorCode)
    }

    private fun sessionFrom(json: Map<*, *>?): SignInSession {
        requireNotNull(json) { "Supabase returned an empty response." }
        val user = json["user"] as? Map<*, *> ?: error("Supabase did not return a user.")
        return SignInSession(
            accessToken = json["access_token"] as? String ?: error("Supabase did not return a session."),
            refreshToken = json["refresh_token"] as? String ?: error("Supabase did not return a refresh token."),
            user = SignedInUser(user["id"] as? String ?: error("Supabase user ID missing."), user["email"] as? String),
        )
    }

    suspend fun signIn(email: String, password: String): Result<SignInSession> = withContext(Dispatchers.IO) {
        runCatching {
            sessionFrom(post("/auth/v1/token?grant_type=password", mapOf("email" to email.trim(), "password" to password), "Sign-in failed"))
        }
    }

    suspend fun signUp(email: String, password: String): Result<SignUpOutcome> = withContext(Dispatchers.IO) {
        runCatching {
            val payload = mapOf(
                "email" to email.trim(),
                "password" to password,
                "options" to mapOf("emailRedirectTo" to AuthCallback.URI),
            )
            val json = post("/auth/v1/signup", payload, "Sign-up failed")
            val token = json?.get("access_token") as? String
            if (token != null) SignUpOutcome.SignedIn(sessionFrom(json))
            else SignUpOutcome.ConfirmEmail(email.trim())
        }
    }

    suspend fun resendConfirmation(email: String): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            post(
                "/auth/v1/resend",
                mapOf("type" to "signup", "email" to email.trim(), "email_redirect_to" to AuthCallback.URI),
                "Could not resend the confirmation email",
            )
            Unit
        }
    }

    suspend fun sendPasswordReset(email: String): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            post("/auth/v1/recover", mapOf("email" to email.trim()), "Could not send the password reset email")
            Unit
        }
    }

    fun googleIntent(context: Context): Intent {
        requireConfigured()
        val verifier = ByteArray(32).also { SecureRandom().nextBytes(it) }
            .let { Base64.encodeToString(it, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP) }
        val challenge = MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray())
            .let { Base64.encodeToString(it, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP) }
        AuthSessionStore(context).savePkceVerifier(verifier)
        val uri = Uri.parse("${base()}/auth/v1/authorize").buildUpon()
            .appendQueryParameter("provider", "google")
            .appendQueryParameter("redirect_to", AuthCallback.URI)
            .appendQueryParameter("code_challenge", challenge)
            .appendQueryParameter("code_challenge_method", "s256")
            .build()
        return Intent(Intent.ACTION_VIEW, uri)
    }

    suspend fun completeGoogle(context: Context, callback: Uri): Result<SignInSession> = withContext(Dispatchers.IO) {
        runCatching {
            val code = callback.getQueryParameter("code")
                ?: error(callback.getQueryParameter("error_description") ?: "Google sign-in did not return a code.")
            val verifier = AuthSessionStore(context).takePkceVerifier()
                ?: error("The sign-in verifier was unavailable. Start Google sign-in again.")
            sessionFrom(post("/auth/v1/token?grant_type=pkce", mapOf("auth_code" to code, "code_verifier" to verifier), "Google sign-in failed"))
        }
    }

    suspend fun refresh(refreshToken: String): Result<SignInSession> = withContext(Dispatchers.IO) {
        runCatching {
            sessionFrom(post("/auth/v1/token?grant_type=refresh_token", mapOf("refresh_token" to refreshToken), "Session refresh failed"))
        }
    }
}
