package com.mindmesh.companion.auth

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthCallbackTest {
    @Test
    fun cloneCallbackReturnsToNativeCompanion() {
        assertTrue(AuthCallback.matches("mindmeshclone", "auth", "/callback"))
        assertFalse(AuthCallback.matches("http", "localhost", "/auth/callback"))
        assertFalse(AuthCallback.matches("mindmesh", "auth", "/callback"))
        assertFalse(AuthCallback.matches("mindmeshclone", "auth", "/other"))
    }
}
