package com.mindmesh.companion.data

import androidx.room.Entity
import androidx.room.PrimaryKey

/** Persisted states a shared link moves through. Drives every status label in the UI. */
object SaveStates {
    /** Stored locally; the worker has not uploaded it yet. */
    const val QUEUED = "queued"

    /** The upload request is in flight. */
    const val UPLOADING = "uploading"

    /** The backend accepted the save and returned a job id. */
    const val ACCEPTED = "accepted"

    /** The backend is processing the save (download, transcription, indexing). */
    const val PROCESSING = "processing"

    /** The backend finished; the save is in the MindMesh library. */
    const val SYNCED = "synced"

    /** The backend rejected or failed the save. Manual retry available. */
    const val FAILED = "failed"

    /** No route to the backend (Docker/API down, wrong URL, no network). */
    const val OFFLINE = "offline"

    /** The stored session was rejected; the user must sign in again. */
    const val AUTH_ERROR = "auth_error"

    val UPLOADABLE = listOf(QUEUED)
    val IN_FLIGHT = listOf(UPLOADING, ACCEPTED, PROCESSING)
    val UNRESOLVED = listOf(QUEUED, UPLOADING, ACCEPTED, PROCESSING, OFFLINE, AUTH_ERROR)
}

@Entity(tableName = "quick_saves")
data class QuickSave(
    @PrimaryKey val id: String,
    val ownerId: String,
    val url: String,
    val source: String,
    val state: String = SaveStates.QUEUED,
    val jobId: String? = null,
    val message: String = "Saved on this device — waiting to sync.",
    val attempts: Int = 0,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
)
