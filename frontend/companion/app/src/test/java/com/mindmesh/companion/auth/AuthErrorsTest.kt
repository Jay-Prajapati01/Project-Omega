package com.mindmesh.companion.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class AuthErrorsTest {
    @Test
    fun `invalid credentials message`() {
        val message = AuthErrors.friendly(400, "Invalid login credentials", "invalid_credentials", "Sign in failed")
        assertEquals("Email or password is incorrect.", message)
    }

    @Test
    fun `unconfirmed email message`() {
        val message = AuthErrors.friendly(400, "Email not confirmed", "email_not_confirmed", "Sign in failed")
        assertEquals("Confirm your email first — the confirmation link is in your inbox.", message)
    }

    @Test
    fun `existing account message`() {
        val message = AuthErrors.friendly(400, "User already registered", "user_already_exists", "Sign up failed")
        assertEquals("An account with this email already exists. Sign in instead.", message)
    }

    @Test
    fun `weak password message`() {
        val message = AuthErrors.friendly(400, "Password should be at least 8 characters", "weak_password", "Sign up failed")
        assertEquals("Use a password with at least 8 characters.", message)
    }

    @Test
    fun `expired session message`() {
        val message = AuthErrors.friendly(401, "JWT expired", null, "Sign in failed")
        assertEquals("Your session is no longer valid. Sign in again.", message)
    }

    @Test
    fun `rate limit message`() {
        val message = AuthErrors.friendly(429, null, null, "Sign in failed")
        assertEquals("Too many attempts. Wait a minute and try again.", message)
    }

    @Test
    fun `503 keeps the backend detail when it has one`() {
        assertEquals("AUTH_CONFIGURATION_REQUIRED", AuthErrors.friendly(503, "AUTH_CONFIGURATION_REQUIRED", null, "Sign in failed"))
        assertEquals(
            "MindMesh authentication is temporarily unavailable.",
            AuthErrors.friendly(503, null, null, "Sign in failed"),
        )
    }

    @Test
    fun `unknown status falls back to the caller message`() {
        assertEquals("Sign in failed (HTTP 500).", AuthErrors.friendly(500, null, null, "Sign in failed"))
        assertEquals("Sign in failed: boom", AuthErrors.friendly(418, "boom", null, "Sign in failed"))
    }

    @Test
    fun `network failures are detected through the cause chain`() {
        assertTrue(AuthErrors.isNetworkFailure(IOException("timeout")))
        assertTrue(AuthErrors.isNetworkFailure(RuntimeException(IOException("dns"))))
        assertFalse(AuthErrors.isNetworkFailure(IllegalStateException("bad state")))
        assertFalse(AuthErrors.isNetworkFailure(null))
    }

    @Test
    fun `not-configured message points at local properties`() {
        assertTrue(AuthErrors.notConfigured().contains("local.properties"))
    }
}
