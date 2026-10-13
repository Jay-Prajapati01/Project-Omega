package com.mindmesh.companion.sync

import com.mindmesh.companion.data.SaveStates

/** Where a save stands right now, plus the sentence the user will read. */
data class SyncOutcome(val state: String, val message: String, val retryable: Boolean)

/**
 * Pure mapping from backend answers to save states, so the UI always tells the
 * truth about what happened to a shared link — including "your backend is not
 * running" instead of a permanent, silent "syncing…".
 */
object SyncOutcomes {
    const val OFFLINE_MESSAGE = "MindMesh backend unreachable — start the backend (Docker) and tap Retry."
    const val UNREACHABLE_MESSAGE = "MindMesh backend unreachable — retrying automatically."
    const val OFFLINE_AUTH_MESSAGE = "Could not refresh your session — check your connection."
    const val ACCEPTED_MESSAGE = "Accepted by MindMesh — processing now."
    const val PROCESSING_MESSAGE = "MindMesh is processing this save."
    const val SYNCED_MESSAGE = "Synced — this save is in your MindMesh library."
    const val UPLOADING_MESSAGE = "Sending to MindMesh…"
    const val QUEUED_MESSAGE = "Saved on this device — waiting to upload."
    const val AUTH_MESSAGE = "MindMesh rejected this session — sign in again to finish syncing."
    const val NO_JOB_MESSAGE = "Accepted by MindMesh, but no job id came back."
    const val STILL_PROCESSING_MESSAGE = "Still processing in the background — this save is safe with MindMesh."

    fun queued(): SyncOutcome = SyncOutcome(SaveStates.QUEUED, QUEUED_MESSAGE, retryable = true)

    fun uploading(): SyncOutcome = SyncOutcome(SaveStates.UPLOADING, UPLOADING_MESSAGE, retryable = true)

    fun offline(detail: String? = null): SyncOutcome =
        SyncOutcome(SaveStates.OFFLINE, detail ?: OFFLINE_MESSAGE, retryable = true)

    fun accepted(jobId: String?, resourceMessage: String? = null): SyncOutcome =
        if (jobId.isNullOrBlank()) failed(NO_JOB_MESSAGE)
        else SyncOutcome(SaveStates.ACCEPTED, resourceMessage ?: ACCEPTED_MESSAGE, retryable = false)

    fun authError(): SyncOutcome = SyncOutcome(SaveStates.AUTH_ERROR, AUTH_MESSAGE, retryable = false)

    fun synced(): SyncOutcome = SyncOutcome(SaveStates.SYNCED, SYNCED_MESSAGE, retryable = false)

    fun failed(message: String?): SyncOutcome =
        SyncOutcome(SaveStates.FAILED, message?.takeIf { it.isNotBlank() } ?: "MindMesh could not save this link.", retryable = false)

    /** Maps an HTTP failure from POST /mobile/quick-saves. */
    fun forHttp(code: Int, detail: String?, errorCode: String?): SyncOutcome {
        val cleanCode = errorCode.orEmpty()
        val cleanDetail = detail?.takeIf { it.isNotBlank() }
        return when {
            cleanCode == "AUTH_CONFIGURATION_REQUIRED" ->
                failed("$cleanDetail Companion saves need a backend started with AUTH_ENABLED=true.")
            cleanCode == "QUOTA_EXCEEDED" ->
                failed(cleanDetail ?: "This plan's allowance for this source type has been used. Choose a plan with more capacity, then try again.")
            cleanCode == "RATE_LIMITED" ->
                SyncOutcome(SaveStates.QUEUED, cleanDetail ?: "MindMesh is receiving requests quickly — retrying after the server cooldown.", retryable = true)
            code == 401 ->
                authError()
            code == 403 ->
                failed(cleanDetail ?: "This account has no active MindMesh workspace.")
            code == 404 ->
                failed(cleanDetail ?: "The quick-save endpoint was not found — check MINDMESH_API_BASE_URL.")
            code == 400 || code == 409 || code == 413 || code == 422 ->
                failed(cleanDetail ?: "MindMesh rejected this link (HTTP $code).")
            code == 429 || code >= 500 ->
                SyncOutcome(SaveStates.QUEUED, "MindMesh is busy (HTTP $code) — retrying automatically.", retryable = true)
            else ->
                failed(cleanDetail ?: "Upload failed (HTTP $code).")
        }
    }

    /** Maps GET /mobile/quick-saves/{jobId} into the terminal or in-flight state. */
    fun forJob(status: String?, errorMessage: String?): SyncOutcome = when (status?.lowercase()) {
        "completed", "succeeded", "done", "success" -> synced()
        "failed", "error", "cancelled", "canceled" ->
            failed(errorMessage ?: "MindMesh could not process this save. Tap Retry to try again.")
        "queued", "pending", "uploading", "accepted" ->
            SyncOutcome(SaveStates.ACCEPTED, ACCEPTED_MESSAGE, retryable = true)
        else ->
            SyncOutcome(SaveStates.PROCESSING, PROCESSING_MESSAGE, retryable = true)
    }
}
