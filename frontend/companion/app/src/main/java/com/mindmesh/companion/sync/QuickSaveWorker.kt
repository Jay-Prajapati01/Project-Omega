package com.mindmesh.companion.sync

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.mindmesh.companion.auth.AuthErrors
import com.mindmesh.companion.auth.AuthNetworkException
import com.mindmesh.companion.auth.AuthSessionStore
import com.mindmesh.companion.auth.SupabaseAuth
import com.mindmesh.companion.data.MindMeshDatabase
import com.mindmesh.companion.data.QuickSaveDao
import com.mindmesh.companion.data.SaveStates
import com.mindmesh.companion.network.MindMeshApi
import com.mindmesh.companion.network.QuickSaveRequest
import com.mindmesh.companion.network.apiError
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import retrofit2.HttpException

/**
 * Uploads queued saves to the backend and then polls each job until the app can
 * tell the user, without opening the website, whether the link really landed.
 * Every outcome — including "backend not running" — is written back to Room so
 * the Home screen simply renders the truth.
 */
class QuickSaveWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val session = AuthSessionStore(applicationContext)
        val dao = MindMeshDatabase.create(applicationContext).quickSaves()
        val refreshToken = session.refreshToken
        if (refreshToken.isNullOrBlank()) {
            markAuthError(dao, "Sign in to MindMesh so shared links can be synced.")
            return Result.failure()
        }

        val auth = SupabaseAuth.refresh(refreshToken).getOrElse { error ->
            return when {
                error is AuthNetworkException || AuthErrors.isNetworkFailure(error) -> {
                    markOffline(dao, SyncOutcomes.OFFLINE_AUTH_MESSAGE)
                    Result.retry()
                }
                else -> {
                    Log.w(TAG, "session refresh rejected: ${error.message}")
                    markAuthError(dao, SyncOutcomes.AUTH_MESSAGE)
                    Result.failure()
                }
            }
        }
        session.save(auth.user.id, auth.user.email, auth.accessToken, auth.refreshToken)
        dao.requeueAuthErrors()

        val api = MindMeshApi.create { auth.accessToken }
        var needsRetry = false
        var sessionDead = false

        for (item in dao.byStates(listOf(SaveStates.QUEUED, SaveStates.OFFLINE))) {
            dao.setState(item.id, SaveStates.UPLOADING, SyncOutcomes.UPLOADING_MESSAGE)
            val key = if (item.attempts <= 0) item.id else "${item.id}-${item.attempts}"
            var jobId: String? = null
            val outcome = try {
                val receipt = api.quickSave(key, QuickSaveRequest(item.url))
                jobId = receipt.job_id
                val resourceMessage = when (receipt.resource_notice?.provider) {
                    "byok" -> "MindMesh accepted this save — processing uses your connected AI key."
                    "managed" -> "MindMesh accepted this save — processing uses MindMesh managed resources."
                    else -> null
                }
                SyncOutcomes.accepted(receipt.job_id, resourceMessage)
            } catch (error: HttpException) {
                val body = error.apiError()
                SyncOutcomes.forHttp(error.code(), body.detail, body.errorCode)
            } catch (error: IOException) {
                SyncOutcomes.offline()
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                Log.e(TAG, "upload failed for ${item.id}", error)
                SyncOutcomes.failed("Unexpected upload error: ${error.message ?: error.javaClass.simpleName}")
            }

            when {
                outcome.state == SaveStates.ACCEPTED -> dao.setAccepted(item.id, outcome.state, outcome.message, jobId)
                else -> dao.setState(item.id, outcome.state, outcome.message)
            }
            if (outcome.retryable) needsRetry = true
            if (outcome.state == SaveStates.AUTH_ERROR) sessionDead = true
        }

        if (sessionDead) return Result.failure()

        var stillInFlight = false
        for (item in dao.byStates(SaveStates.IN_FLIGHT)) {
            val jobId = item.jobId
            if (jobId.isNullOrBlank()) {
                dao.setState(item.id, SaveStates.FAILED, SyncOutcomes.NO_JOB_MESSAGE)
                continue
            }
            var terminal = false
            for (attempt in 0 until POLLS_PER_RUN) {
                val outcome = pollOnce(api, jobId)
                if (outcome.state == SaveStates.ACCEPTED || outcome.state == SaveStates.PROCESSING) {
                    dao.setState(item.id, outcome.state, outcome.message)
                } else {
                    dao.setState(item.id, outcome.state, outcome.message)
                    terminal = true
                }
                if (outcome.state == SaveStates.AUTH_ERROR) return Result.failure()
                if (terminal) break
                if (attempt < POLLS_PER_RUN - 1) delay(POLL_DELAY_MS)
            }
            if (!terminal) stillInFlight = true
        }

        val unresolved = dao.byStates(SaveStates.UNRESOLVED).isNotEmpty()
        return when {
            needsRetry || stillInFlight || unresolved ->
                if (runAttemptCount >= MAX_ATTEMPTS) Result.success() else Result.retry()
            else -> Result.success()
        }
    }

    private suspend fun pollOnce(api: MindMeshApi, jobId: String): SyncOutcome = try {
        val status = api.status(jobId)
        SyncOutcomes.forJob(status.status, status.error?.message)
    } catch (error: HttpException) {
        val body = error.apiError()
        when {
            error.code() == 401 -> SyncOutcomes.authError()
            error.code() == 404 -> SyncOutcomes.failed("MindMesh no longer knows this save — tap Retry to send it again.")
            error.code() == 429 || error.code() >= 500 ->
                SyncOutcome(SaveStates.ACCEPTED, "MindMesh is busy (HTTP ${error.code()}) — checking again.", retryable = true)
            else -> SyncOutcome(SaveStates.ACCEPTED, body.detail ?: "Status check failed (HTTP ${error.code()}).", retryable = true)
        }
    } catch (error: IOException) {
        SyncOutcome(SaveStates.ACCEPTED, SyncOutcomes.UNREACHABLE_MESSAGE, retryable = true)
    } catch (error: CancellationException) {
        throw error
    } catch (error: Exception) {
        Log.e(TAG, "status poll failed for $jobId", error)
        SyncOutcome(SaveStates.ACCEPTED, "Could not read the save status — checking again.", retryable = true)
    }

    private suspend fun markAuthError(dao: QuickSaveDao, message: String) {
        for (item in dao.byStates(SaveStates.UNRESOLVED)) dao.setState(item.id, SaveStates.AUTH_ERROR, message)
    }

    private suspend fun markOffline(dao: QuickSaveDao, message: String) {
        for (item in dao.byStates(SaveStates.UNRESOLVED)) dao.setState(item.id, SaveStates.OFFLINE, message)
    }

    companion object {
        private const val TAG = "MindMeshSync"
        private const val WORK_NAME = "mindmesh-quick-save"
        private const val POLLS_PER_RUN = 4
        private const val POLL_DELAY_MS = 2_500L
        private const val MAX_ATTEMPTS = 40

        fun enqueue(context: Context, replace: Boolean = false) {
            val request = OneTimeWorkRequestBuilder<QuickSaveWorker>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setBackoffCriteria(BackoffPolicy.LINEAR, 15, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_NAME,
                if (replace) ExistingWorkPolicy.REPLACE else ExistingWorkPolicy.KEEP,
                request,
            )
        }
    }
}
