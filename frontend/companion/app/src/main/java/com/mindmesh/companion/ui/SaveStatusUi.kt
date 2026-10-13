package com.mindmesh.companion.ui

/** Presentation facts for a save state, kept free of Compose so they stay testable. */
data class SaveStatusUi(val label: String, val tone: Tone) {
    enum class Tone { NEUTRAL, INFO, WARNING, SUCCESS, DANGER }

    companion object {
        fun forState(state: String): SaveStatusUi = when (state) {
            com.mindmesh.companion.data.SaveStates.QUEUED -> SaveStatusUi("On device", Tone.NEUTRAL)
            com.mindmesh.companion.data.SaveStates.UPLOADING -> SaveStatusUi("Sending", Tone.INFO)
            com.mindmesh.companion.data.SaveStates.ACCEPTED -> SaveStatusUi("Accepted", Tone.INFO)
            com.mindmesh.companion.data.SaveStates.PROCESSING -> SaveStatusUi("Processing", Tone.WARNING)
            com.mindmesh.companion.data.SaveStates.SYNCED -> SaveStatusUi("Synced", Tone.SUCCESS)
            com.mindmesh.companion.data.SaveStates.FAILED -> SaveStatusUi("Failed", Tone.DANGER)
            com.mindmesh.companion.data.SaveStates.OFFLINE -> SaveStatusUi("Backend offline", Tone.DANGER)
            com.mindmesh.companion.data.SaveStates.AUTH_ERROR -> SaveStatusUi("Needs sign-in", Tone.DANGER)
            else -> SaveStatusUi(state.ifBlank { "Unknown" }, Tone.NEUTRAL)
        }

        fun canRetry(state: String): Boolean =
            state == com.mindmesh.companion.data.SaveStates.FAILED ||
                state == com.mindmesh.companion.data.SaveStates.OFFLINE ||
                state == com.mindmesh.companion.data.SaveStates.AUTH_ERROR
    }
}
