package com.mindmesh.companion.auth

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** Stores only the verified Supabase session; no service credentials belong on-device. */
class AuthSessionStore(context: Context) {
    private val prefs = EncryptedSharedPreferences.create(
        context, "mindmesh-session",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    val userId: String? get() = prefs.getString("user_id", null)
    val email: String? get() = prefs.getString("email", null)
    val accessToken: String? get() = prefs.getString("access_token", null)
    val refreshToken: String? get() = prefs.getString("refresh_token", null)
    val pkceVerifier: String? get() = prefs.getString("pkce_verifier", null)

    fun save(userId: String, email: String?, accessToken: String, refreshToken: String) = prefs.edit()
        .putString("user_id", userId)
        .putString("email", email)
        .putString("access_token", accessToken)
        .putString("refresh_token", refreshToken)
        .apply()

    fun savePkceVerifier(value: String) = prefs.edit().putString("pkce_verifier", value).apply()

    fun takePkceVerifier(): String? = prefs.getString("pkce_verifier", null)
        .also { prefs.edit().remove("pkce_verifier").apply() }

    fun clear() = prefs.edit().clear().apply()
}
