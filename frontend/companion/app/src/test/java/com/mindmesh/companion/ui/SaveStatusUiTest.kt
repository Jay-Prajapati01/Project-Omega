package com.mindmesh.companion.ui

import com.mindmesh.companion.data.SaveStates
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SaveStatusUiTest {
    @Test
    fun `every known state has a label and a tone`() {
        val expected = mapOf(
            SaveStates.QUEUED to ("On device" to SaveStatusUi.Tone.NEUTRAL),
            SaveStates.UPLOADING to ("Sending" to SaveStatusUi.Tone.INFO),
            SaveStates.ACCEPTED to ("Accepted" to SaveStatusUi.Tone.INFO),
            SaveStates.PROCESSING to ("Processing" to SaveStatusUi.Tone.WARNING),
            SaveStates.SYNCED to ("Synced" to SaveStatusUi.Tone.SUCCESS),
            SaveStates.FAILED to ("Failed" to SaveStatusUi.Tone.DANGER),
            SaveStates.OFFLINE to ("Backend offline" to SaveStatusUi.Tone.DANGER),
            SaveStates.AUTH_ERROR to ("Needs sign-in" to SaveStatusUi.Tone.DANGER),
        )
        expected.forEach { (state, pair) ->
            val ui = SaveStatusUi.forState(state)
            assertEquals(pair.first, ui.label)
            assertEquals(pair.second, ui.tone)
        }
    }

    @Test
    fun `unknown state never crashes`() {
        val ui = SaveStatusUi.forState("something_new")
        assertEquals("something_new", ui.label)
        assertEquals(SaveStatusUi.Tone.NEUTRAL, ui.tone)
        assertEquals("Unknown", SaveStatusUi.forState("").label)
    }

    @Test
    fun `retry is offered exactly where it can help`() {
        assertTrue(SaveStatusUi.canRetry(SaveStates.FAILED))
        assertTrue(SaveStatusUi.canRetry(SaveStates.OFFLINE))
        assertTrue(SaveStatusUi.canRetry(SaveStates.AUTH_ERROR))
        assertFalse(SaveStatusUi.canRetry(SaveStates.SYNCED))
        assertFalse(SaveStatusUi.canRetry(SaveStates.QUEUED))
        assertFalse(SaveStatusUi.canRetry(SaveStates.UPLOADING))
        assertFalse(SaveStatusUi.canRetry(SaveStates.ACCEPTED))
        assertFalse(SaveStatusUi.canRetry(SaveStates.PROCESSING))
    }
}
