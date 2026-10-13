package com.mindmesh.companion.sync

import com.mindmesh.companion.data.SaveStates
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncOutcomesTest {
    @Test
    fun `401 becomes a sign-in error`() {
        val outcome = SyncOutcomes.forHttp(401, "invalid JWT", null)
        assertEquals(SaveStates.AUTH_ERROR, outcome.state)
        assertFalse(outcome.retryable)
    }

    @Test
    fun `AUTH_CONFIGURATION_REQUIRED explains the missing backend flag`() {
        val outcome = SyncOutcomes.forHttp(503, "AUTH_CONFIGURATION_REQUIRED", "AUTH_CONFIGURATION_REQUIRED")
        assertEquals(SaveStates.FAILED, outcome.state)
        assertTrue(outcome.message.contains("AUTH_ENABLED=true"))
    }

    @Test
    fun `404 points at the base url`() {
        val outcome = SyncOutcomes.forHttp(404, null, null)
        assertEquals(SaveStates.FAILED, outcome.state)
        assertTrue(outcome.message.contains("MINDMESH_API_BASE_URL"))
    }

    @Test
    fun `400 rejects with the backend detail when present`() {
        val outcome = SyncOutcomes.forHttp(400, "Only http(s) links are supported.", null)
        assertEquals(SaveStates.FAILED, outcome.state)
        assertEquals("Only http(s) links are supported.", outcome.message)
    }

    @Test
    fun `5xx stays queued for automatic retry`() {
        val outcome = SyncOutcomes.forHttp(503, null, null)
        assertEquals(SaveStates.QUEUED, outcome.state)
        assertTrue(outcome.retryable)
    }

    @Test
    fun `429 stays queued for automatic retry`() {
        val outcome = SyncOutcomes.forHttp(429, null, null)
        assertEquals(SaveStates.QUEUED, outcome.state)
        assertTrue(outcome.retryable)
    }

    @Test
    fun `unknown status maps to failed with the http code`() {
        val outcome = SyncOutcomes.forHttp(418, null, null)
        assertEquals(SaveStates.FAILED, outcome.state)
        assertTrue(outcome.message.contains("418"))
    }

    @Test
    fun `completed job is synced`() {
        val outcome = SyncOutcomes.forJob("completed", null)
        assertEquals(SaveStates.SYNCED, outcome.state)
        assertEquals(SyncOutcomes.SYNCED_MESSAGE, outcome.message)
    }

    @Test
    fun `failed job surfaces the backend error`() {
        val outcome = SyncOutcomes.forJob("failed", "Could not fetch the reel")
        assertEquals(SaveStates.FAILED, outcome.state)
        assertEquals("Could not fetch the reel", outcome.message)
    }

    @Test
    fun `queued job stays accepted and retryable`() {
        val outcome = SyncOutcomes.forJob("queued", null)
        assertEquals(SaveStates.ACCEPTED, outcome.state)
        assertTrue(outcome.retryable)
    }

    @Test
    fun `unknown job status is processing`() {
        val outcome = SyncOutcomes.forJob(null, null)
        assertEquals(SaveStates.PROCESSING, outcome.state)
        assertEquals(SyncOutcomes.PROCESSING_MESSAGE, outcome.message)
    }

    @Test
    fun `accepted without a job id is a failure, never a silent success`() {
        val outcome = SyncOutcomes.accepted(null)
        assertEquals(SaveStates.FAILED, outcome.state)
        assertEquals(SyncOutcomes.NO_JOB_MESSAGE, outcome.message)
    }

    @Test
    fun `offline keeps the caller detail`() {
        assertEquals("boom", SyncOutcomes.offline("boom").message)
        assertEquals(SyncOutcomes.OFFLINE_MESSAGE, SyncOutcomes.offline().message)
        assertEquals(SaveStates.OFFLINE, SyncOutcomes.offline().state)
    }

    @Test
    fun `failed falls back to a generic message`() {
        assertEquals("MindMesh could not save this link.", SyncOutcomes.failed(null).message)
        assertEquals("MindMesh could not save this link.", SyncOutcomes.failed("  ").message)
    }
}
