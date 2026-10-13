package com.mindmesh.companion

import android.app.Application
import android.net.Uri
import android.util.Patterns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.mindmesh.companion.auth.AuthErrors
import com.mindmesh.companion.auth.AuthNetworkException
import com.mindmesh.companion.auth.AuthSessionStore
import com.mindmesh.companion.auth.SignUpOutcome
import com.mindmesh.companion.auth.SupabaseAuth
import com.mindmesh.companion.data.MindMeshDatabase
import com.mindmesh.companion.data.QuickSave
import com.mindmesh.companion.data.SaveStates
import com.mindmesh.companion.network.BackendHealth
import com.mindmesh.companion.network.EntitlementsResponse
import com.mindmesh.companion.network.MindMeshApi
import com.mindmesh.companion.share.SharedUrlParser
import com.mindmesh.companion.sync.QuickSaveWorker
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** Destination of the companion's small state machine. */
enum class Screen { WELCOME, LOGIN, SIGNUP, VERIFY, HOME }

/** Session truth. A stored user id alone never counts as signed in. */
sealed interface AuthUiState {
    data object Restoring : AuthUiState
    data class SignedIn(val userId: String, val email: String?) : AuthUiState
    data class SignedOut(val reason: String? = null) : AuthUiState
}

/** One-shot message rendered as a banner. */
data class UiNotice(val kind: Kind, val text: String) {
    enum class Kind { INFO, SUCCESS, WARNING, ERROR }
}

/**
 * Owns authentication, the save queue, backend reachability and every message
 * the UI shows, so screens stay declarative and rotation never loses state.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val context = application.applicationContext
    val session = AuthSessionStore(context)
    private val dao = MindMeshDatabase.create(context).quickSaves()

    private val _auth = MutableStateFlow<AuthUiState>(
        if (session.userId.isNullOrBlank()) AuthUiState.SignedOut() else AuthUiState.Restoring,
    )
    val auth: StateFlow<AuthUiState> = _auth.asStateFlow()

    private val _screen = MutableStateFlow(if (session.userId.isNullOrBlank()) Screen.WELCOME else Screen.HOME)
    val screen: StateFlow<Screen> = _screen.asStateFlow()

    private val _draftUrl = MutableStateFlow("")
    val draftUrl: StateFlow<String> = _draftUrl.asStateFlow()

    private val _notice = MutableStateFlow<UiNotice?>(null)
    val notice: StateFlow<UiNotice?> = _notice.asStateFlow()

    private val _backend = MutableStateFlow<BackendHealth.Status>(BackendHealth.Status.Checking)
    val backend: StateFlow<BackendHealth.Status> = _backend.asStateFlow()

    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()
    private val _entitlements = MutableStateFlow<EntitlementsResponse?>(null)
    val entitlements: StateFlow<EntitlementsResponse?> = _entitlements.asStateFlow()
    private val _darkTheme = MutableStateFlow(context.getSharedPreferences("mindmesh-ui", 0).getBoolean("dark_theme", false))
    val darkTheme: StateFlow<Boolean> = _darkTheme.asStateFlow()

    private val _verifyEmail = MutableStateFlow("")
    val verifyEmail: StateFlow<String> = _verifyEmail.asStateFlow()

    private val _owner = MutableStateFlow(session.userId.orEmpty())
    private val _pendingShare = MutableStateFlow<String?>(null)
    private var lastGoogleCode: String? = null

    val saves: StateFlow<List<QuickSave>> = _owner
        .flatMapLatest { owner -> dao.observe(owner) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init {
        if (!session.userId.isNullOrBlank()) {
            restoreSession()
            QuickSaveWorker.enqueue(context)
        }
        checkBackend()
    }

    // --- session -----------------------------------------------------------

    fun restoreSession() {
        val userId = session.userId
        val refreshToken = session.refreshToken
        if (userId.isNullOrBlank() || refreshToken.isNullOrBlank()) {
            _auth.value = AuthUiState.SignedOut()
            _owner.value = ""
            return
        }
        viewModelScope.launch {
            SupabaseAuth.refresh(refreshToken)
                .onSuccess { current ->
                    session.save(current.user.id, current.user.email, current.accessToken, current.refreshToken)
                    acceptSession(current.user.id, current.user.email)
                }
                .onFailure { error ->
                    if (error is AuthNetworkException || AuthErrors.isNetworkFailure(error)) {
                        acceptSession(userId, session.email)
                        setNotice(UiNotice.Kind.WARNING, "You appear to be offline. MindMesh will verify your session as soon as it can reach Supabase.")
                    } else {
                        expireSession("Your MindMesh session expired. Sign in again to keep syncing.")
                    }
                }
        }
    }

    fun signIn(email: String, password: String) {
        if (email.isBlank() || password.isBlank()) {
            setNotice(UiNotice.Kind.ERROR, "Enter your email and password.")
            return
        }
        viewModelScope.launch {
            _busy.value = true
            _notice.value = null
            SupabaseAuth.signIn(email, password)
                .onSuccess { current ->
                    session.save(current.user.id, current.user.email, current.accessToken, current.refreshToken)
                    setNotice(UiNotice.Kind.SUCCESS, "Signed in as ${current.user.email ?: email.trim()}.")
                    acceptSession(current.user.id, current.user.email)
                }
                .onFailure { error -> setNotice(UiNotice.Kind.ERROR, error.message ?: "Sign-in failed.") }
            _busy.value = false
        }
    }

    fun signUp(email: String, password: String, confirm: String) {
        val trimmed = email.trim()
        when {
            !Patterns.EMAIL_ADDRESS.matcher(trimmed).matches() -> {
                setNotice(UiNotice.Kind.ERROR, "Enter a valid email address.")
                return
            }
            password.length < 8 -> {
                setNotice(UiNotice.Kind.ERROR, "Use a password with at least 8 characters.")
                return
            }
            password != confirm -> {
                setNotice(UiNotice.Kind.ERROR, "The passwords do not match.")
                return
            }
        }
        viewModelScope.launch {
            _busy.value = true
            _notice.value = null
            SupabaseAuth.signUp(trimmed, password)
                .onSuccess { outcome ->
                    when (outcome) {
                        is SignUpOutcome.SignedIn -> {
                            val current = outcome.session
                            session.save(current.user.id, current.user.email, current.accessToken, current.refreshToken)
                            setNotice(UiNotice.Kind.SUCCESS, "Account ready. Welcome to MindMesh.")
                            acceptSession(current.user.id, current.user.email)
                        }
                        is SignUpOutcome.ConfirmEmail -> {
                            _verifyEmail.value = outcome.email
                            _screen.value = Screen.VERIFY
                            setNotice(UiNotice.Kind.INFO, "Check ${outcome.email} and confirm your address to finish signup.")
                        }
                    }
                }
                .onFailure { error -> setNotice(UiNotice.Kind.ERROR, error.message ?: "Sign-up failed.") }
            _busy.value = false
        }
    }

    fun resendConfirmation() {
        val email = _verifyEmail.value
        if (email.isBlank()) return
        viewModelScope.launch {
            _busy.value = true
            SupabaseAuth.resendConfirmation(email)
                .onSuccess { setNotice(UiNotice.Kind.SUCCESS, "Confirmation email sent to $email.") }
                .onFailure { error -> setNotice(UiNotice.Kind.ERROR, error.message ?: "Could not resend the email.") }
            _busy.value = false
        }
    }

    fun sendPasswordReset(email: String) {
        val trimmed = email.trim()
        if (!Patterns.EMAIL_ADDRESS.matcher(trimmed).matches()) {
            setNotice(UiNotice.Kind.ERROR, "Enter your account email first, then tap Forgot password.")
            return
        }
        viewModelScope.launch {
            _busy.value = true
            SupabaseAuth.sendPasswordReset(trimmed)
                .onSuccess { setNotice(UiNotice.Kind.INFO, "If $trimmed has a MindMesh account, a reset link is on its way.") }
                .onFailure { error -> setNotice(UiNotice.Kind.ERROR, error.message ?: "Could not send the reset email.") }
            _busy.value = false
        }
    }

    fun completeGoogle(callback: Uri) {
        viewModelScope.launch {
            _busy.value = true
            SupabaseAuth.completeGoogle(context, callback)
                .onSuccess { current ->
                    session.save(current.user.id, current.user.email, current.accessToken, current.refreshToken)
                    setNotice(UiNotice.Kind.SUCCESS, "Signed in with Google as ${current.user.email ?: "your account"}.")
                    acceptSession(current.user.id, current.user.email)
                }
                .onFailure { error -> setNotice(UiNotice.Kind.ERROR, error.message ?: "Google sign-in failed.") }
            _busy.value = false
        }
    }

    /** Handles the mindmeshclone://auth/callback deep link, ignoring duplicates. */
    fun onAuthCallback(callback: Uri) {
        val code = callback.getQueryParameter("code")
        if (code != null && code == lastGoogleCode) return
        lastGoogleCode = code
        completeGoogle(callback)
    }

    /** Forces a sync pass right now instead of waiting for WorkManager's backoff. */
    fun syncNow() {
        QuickSaveWorker.enqueue(context, replace = true)
        checkBackend()
        setNotice(UiNotice.Kind.INFO, "Sync requested — statuses below update as the backend answers.")
    }

    fun signOut(reason: String? = null) {
        session.clear()
        _owner.value = ""
        _auth.value = AuthUiState.SignedOut(reason)
        _screen.value = Screen.WELCOME
        setNotice(UiNotice.Kind.INFO, reason ?: "Signed out on this device.")
    }

    private fun expireSession(reason: String) {
        session.clear()
        _owner.value = ""
        _auth.value = AuthUiState.SignedOut(reason)
        _screen.value = Screen.WELCOME
        setNotice(UiNotice.Kind.ERROR, reason)
    }

    private fun acceptSession(userId: String, email: String?) {
        _auth.value = AuthUiState.SignedIn(userId, email)
        _owner.value = userId
        _screen.value = Screen.HOME
        viewModelScope.launch(Dispatchers.IO) { dao.requeueAuthErrors() }
        QuickSaveWorker.enqueue(context)
        checkBackend()
        refreshEntitlements()
        _pendingShare.value?.let { shared ->
            _draftUrl.value = shared
            _pendingShare.value = null
            setNotice(UiNotice.Kind.INFO, "Link from ${source(shared).replaceFirstChar { it.uppercase() }} is ready — tap Save to MindMesh.")
        }
    }

    /** Reads the same account plan and limits that the website displays. */
    fun refreshEntitlements() {
        val token = session.accessToken ?: return
        viewModelScope.launch(Dispatchers.IO) {
            runCatching { MindMeshApi.create { token }.entitlements() }
                .onSuccess { _entitlements.value = it }
                .onFailure { /* Existing save/sync flow stays available when commerce is not deployed yet. */ }
        }
    }

    // --- shared links ------------------------------------------------------

    /** Called when an ACTION_SEND intent delivers a link into the app. */
    fun onSharedLink(url: String?) {
        if (url.isNullOrBlank()) {
            if (_auth.value is AuthUiState.SignedIn) {
                setNotice(UiNotice.Kind.WARNING, "No link came through with that share. Paste it into the field and tap Save.")
            } else {
                setNotice(UiNotice.Kind.WARNING, "That share did not include a link. After signing in you can paste it here.")
            }
            return
        }
        _draftUrl.value = url
        val signedIn = _auth.value is AuthUiState.SignedIn
        if (signedIn) {
            _screen.value = Screen.HOME
            setNotice(UiNotice.Kind.INFO, "Link received — tap Save to MindMesh to store it.")
        } else {
            _pendingShare.value = url
            setNotice(UiNotice.Kind.INFO, "Sign in to save the shared link. It is waiting for you.")
        }
    }

    fun setDraft(url: String) {
        _draftUrl.value = url
    }

    fun saveDraft() {
        val url = SharedUrlParser.extract(_draftUrl.value)
        if (url == null) {
            setNotice(UiNotice.Kind.ERROR, "That does not look like a link. Paste a full https://… address.")
            return
        }
        val owner = session.userId
        if (owner.isNullOrBlank()) {
            setNotice(UiNotice.Kind.ERROR, "Sign in before saving links to MindMesh.")
            return
        }
        viewModelScope.launch(Dispatchers.IO) {
            dao.insert(QuickSave(UUID.randomUUID().toString(), owner, url, source(url)))
            QuickSaveWorker.enqueue(context)
        }
        _draftUrl.value = ""
        _screen.value = Screen.HOME
        setNotice(UiNotice.Kind.SUCCESS, "Saved on this device — syncing with MindMesh now. The list below shows the live status.")
    }

    fun retry(item: QuickSave) {
        viewModelScope.launch(Dispatchers.IO) {
            if (item.state == SaveStates.FAILED || item.state == SaveStates.AUTH_ERROR) dao.bumpAttempts(item.id)
            dao.setState(item.id, SaveStates.QUEUED, "Retry requested — waiting to upload.")
            QuickSaveWorker.enqueue(context, replace = true)
        }
        setNotice(UiNotice.Kind.INFO, "Retrying — watch this save's status below.")
    }

    // --- app chrome --------------------------------------------------------

    fun navigate(to: Screen) {
        _screen.value = to
        _notice.value = null
    }

    fun checkBackend() {
        viewModelScope.launch {
            _backend.value = BackendHealth.Status.Checking
            _backend.value = BackendHealth.check()
        }
    }

    fun setNotice(kind: UiNotice.Kind, text: String) {
        _notice.value = UiNotice(kind, text)
    }

    fun dismissNotice() {
        _notice.value = null
    }

    fun toggleTheme() {
        _darkTheme.value = !_darkTheme.value
        context.getSharedPreferences("mindmesh-ui", 0).edit().putBoolean("dark_theme", _darkTheme.value).apply()
    }

    companion object {
        fun source(url: String): String = when {
            "youtube" in url || "youtu.be" in url -> "youtube"
            "instagram" in url -> "instagram"
            else -> "web"
        }
    }
}
