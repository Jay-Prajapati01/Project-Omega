package com.mindmesh.companion.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mindmesh.companion.AuthUiState
import com.mindmesh.companion.BuildConfig
import com.mindmesh.companion.MainViewModel
import com.mindmesh.companion.UiNotice
import com.mindmesh.companion.data.QuickSave
import com.mindmesh.companion.data.SaveStates
import com.mindmesh.companion.network.BackendHealth
import com.mindmesh.companion.ui.SaveStatusUi
import com.mindmesh.companion.ui.components.BrandHeader
import com.mindmesh.companion.ui.components.BrutButton
import com.mindmesh.companion.ui.components.BrutButtonStyle
import com.mindmesh.companion.ui.components.BrutCard
import com.mindmesh.companion.ui.components.BrutTextField
import com.mindmesh.companion.ui.components.Eyebrow
import com.mindmesh.companion.ui.components.NoticeBanner
import com.mindmesh.companion.ui.components.StatusPill
import com.mindmesh.companion.ui.components.ThemeToggle
import com.mindmesh.companion.ui.theme.MindMeshColors
import com.mindmesh.companion.ui.theme.MonoStyle
import com.mindmesh.companion.util.RelativeTime

/**
 * Signed-in surface: receive a shared link, save it, and watch every save's
 * real backend status without leaving the app.
 */
@Composable
fun HomeScreen(vm: MainViewModel, darkTheme: Boolean) {
    val auth by vm.auth.collectAsState()
    val saves by vm.saves.collectAsState()
    val draft by vm.draftUrl.collectAsState()
    val backend by vm.backend.collectAsState()
    val notice by vm.notice.collectAsState()
    val entitlements by vm.entitlements.collectAsState()

    val email = (auth as? AuthUiState.SignedIn)?.email
    val needsSignIn = saves.any { it.state == SaveStates.AUTH_ERROR }
    val counts = remember(saves) { saves.groupingBy { it.state }.eachCount() }
    val synced = counts[SaveStates.SYNCED] ?: 0
    val syncing = (counts[SaveStates.UPLOADING] ?: 0) + (counts[SaveStates.ACCEPTED] ?: 0) + (counts[SaveStates.PROCESSING] ?: 0)
    val attention = (counts[SaveStates.FAILED] ?: 0) + (counts[SaveStates.OFFLINE] ?: 0) + (counts[SaveStates.AUTH_ERROR] ?: 0)

    Column(
        Modifier
            .fillMaxSize()
            .background(MindMeshColors.Paper)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 18.dp),
    ) {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val narrow = maxWidth < 390.dp
            if (narrow) {
                Column(Modifier.fillMaxWidth()) {
                    BrandHeader(Modifier.fillMaxWidth())
                    Spacer(Modifier.height(12.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        ThemeToggle(darkTheme = darkTheme, onToggle = vm::toggleTheme)
                        BrutButton("Sign out", style = BrutButtonStyle.SECONDARY, compact = true, onClick = { vm.signOut() })
                    }
                }
            } else {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    BrandHeader(Modifier.weight(1f))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ThemeToggle(darkTheme = darkTheme, onToggle = vm::toggleTheme)
                        BrutButton("Sign out", style = BrutButtonStyle.SECONDARY, compact = true, onClick = { vm.signOut() })
                    }
                }
            }
        }

        Spacer(Modifier.height(12.dp))
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val narrow = maxWidth < 390.dp
            if (narrow) {
                Column(Modifier.fillMaxWidth()) {
                    Text(email ?: "Your account", style = MaterialTheme.typography.bodySmall, color = MindMeshColors.InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Spacer(Modifier.height(6.dp))
                    BackendChip(backend, onRecheck = vm::checkBackend)
                }
            } else {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        email ?: "Your account",
                        style = MaterialTheme.typography.bodySmall,
                        color = MindMeshColors.InkMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false).padding(end = 8.dp),
                    )
                    BackendChip(backend, onRecheck = vm::checkBackend)
                }
            }
        }
        val backendProblem = when (val status = backend) {
            is BackendHealth.Status.Unreachable -> status.reason
            is BackendHealth.Status.Unexpected -> status.description
            else -> null
        }
        if (backendProblem != null) {
            Spacer(Modifier.height(8.dp))
            Text(backendProblem, style = MaterialTheme.typography.bodySmall, color = MindMeshColors.Danger)
        }

        if (needsSignIn) {
            Spacer(Modifier.height(14.dp))
            NoticeBanner(
                UiNotice.Kind.ERROR,
                "MindMesh rejected the stored session. Sign in again so the remaining saves can finish syncing.",
            )
            Spacer(Modifier.height(8.dp))
            BrutButton("Sign in again", style = BrutButtonStyle.SECONDARY, compact = true, onClick = { vm.signOut("Session expired — sign in again to keep syncing.") })
        }

        entitlements?.let { account ->
            Spacer(Modifier.height(14.dp))
            BrutCard(Modifier.fillMaxWidth()) {
                Eyebrow("Your MindMesh account")
                Spacer(Modifier.height(6.dp))
                Text("${account.effective_plan.replaceFirstChar { it.uppercase() }} plan", style = MaterialTheme.typography.titleLarge, color = MindMeshColors.Ink)
                Spacer(Modifier.height(4.dp))
                Text(if (account.ai_mode == "byok") "Your connected AI key is active for selected tasks." else "MindMesh managed resources are active.", style = MaterialTheme.typography.bodyMedium, color = MindMeshColors.InkMuted)
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    StatusPill("${account.usage["web"]?.remaining ?: 0} web left", MindMeshColors.InfoSoft, MindMeshColors.Info)
                    StatusPill("${account.usage["instagram"]?.remaining ?: 0} reels left", MindMeshColors.SuccessSoft, MindMeshColors.Success)
                }
            }
        }

        notice?.let {
            Spacer(Modifier.height(14.dp))
            NoticeBanner(it.kind, it.text, onDismiss = vm::dismissNotice)
        }

        Spacer(Modifier.height(16.dp))
        BrutCard(Modifier.fillMaxWidth()) {
            Eyebrow("Share to save")
            Spacer(Modifier.height(8.dp))
            Text("Save a link", style = MaterialTheme.typography.titleLarge, color = MindMeshColors.Ink)
            Spacer(Modifier.height(6.dp))
            Text(
                "Share a YouTube or Instagram link to MindMesh. Each save reports its live status here.",
                style = MaterialTheme.typography.bodyMedium,
                color = MindMeshColors.InkMuted,
            )
            Spacer(Modifier.height(14.dp))
            BrutTextField(
                value = draft,
                onValueChange = vm::setDraft,
                label = "Shared link",
                keyboardType = KeyboardType.Uri,
                imeAction = ImeAction.Done,
                onImeAction = { vm.saveDraft() },
                supportingText = "Links shared into MindMesh appear here automatically.",
            )
            Spacer(Modifier.height(14.dp))
            BrutButton("Save to MindMesh", onClick = vm::saveDraft, enabled = draft.isNotBlank())
        }

        Spacer(Modifier.height(16.dp))
        if (saves.isNotEmpty()) {
            Spacer(Modifier.height(16.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SummaryChip("$synced synced", MindMeshColors.SuccessSoft, MindMeshColors.Success)
                SummaryChip("$syncing syncing", MindMeshColors.InfoSoft, MindMeshColors.Info)
                SummaryChip("$attention need attention", if (attention > 0) MindMeshColors.DangerSoft else MindMeshColors.PaperCard, if (attention > 0) MindMeshColors.Danger else MindMeshColors.InkMuted)
            }
        }

        Spacer(Modifier.height(16.dp))
        BrutCard(Modifier.fillMaxWidth()) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Recent saves", style = MaterialTheme.typography.titleMedium, color = MindMeshColors.Ink)
                BrutButton("Sync now", style = BrutButtonStyle.GHOST, compact = true, onClick = vm::syncNow)
            }
            if (saves.isEmpty()) {
                Spacer(Modifier.height(10.dp))
                Text(
                    "Nothing saved yet. Share a reel, short or article to MindMesh and it lands here with a live status.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MindMeshColors.InkMuted,
                )
            } else {
                saves.take(25).forEachIndexed { index, item ->
                    if (index > 0) {
                        Spacer(Modifier.height(10.dp))
                        HorizontalDivider(thickness = 1.5.dp, color = MindMeshColors.PaperCard)
                    }
                    SaveRow(
                        item = item,
                        onRetry = {
                            if (item.state == SaveStates.AUTH_ERROR) {
                                vm.signOut("Session expired — sign in again to keep syncing.")
                            } else {
                                vm.retry(item)
                            }
                        },
                    )
                }
                if (saves.size > 25) {
                    Spacer(Modifier.height(10.dp))
                    Text("…and ${saves.size - 25} older saves", style = MaterialTheme.typography.bodySmall, color = MindMeshColors.InkMuted)
                }
            }
        }

        Spacer(Modifier.height(18.dp))
        Text(
            "MindMesh companion v${BuildConfig.VERSION_NAME} · API ${BuildConfig.API_BASE_URL}",
            style = MonoStyle.copy(fontSize = 11.sp),
            color = MindMeshColors.InkMuted,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(26.dp))
    }
}

@Composable
private fun BackendChip(status: BackendHealth.Status, onRecheck: () -> Unit) {
    val (label, container, color) = when (status) {
        BackendHealth.Status.Checking -> Triple("Checking backend…", MindMeshColors.PaperCard, MindMeshColors.InkMuted)
        is BackendHealth.Status.Online ->
            Triple(if (status.version.isNullOrBlank()) "Backend online" else "Backend online · ${status.version}", MindMeshColors.SuccessSoft, MindMeshColors.Success)
        is BackendHealth.Status.Unreachable -> Triple("Backend offline", MindMeshColors.DangerSoft, MindMeshColors.Danger)
        is BackendHealth.Status.Unexpected -> Triple("Backend error", MindMeshColors.WarningSoft, MindMeshColors.Warning)
    }
    Box(modifier = Modifier.clickable(onClick = onRecheck)) {
        StatusPill(label, container, color)
    }
}

@Composable
private fun SummaryChip(text: String, container: androidx.compose.ui.graphics.Color, content: androidx.compose.ui.graphics.Color) {
    StatusPill(text, container, content)
}

@Composable
private fun SaveRow(item: QuickSave, onRetry: () -> Unit) {
    val status = SaveStatusUi.forState(item.state)
    val (container, color) = when (status.tone) {
        SaveStatusUi.Tone.NEUTRAL -> MindMeshColors.PaperCard to MindMeshColors.Ink
        SaveStatusUi.Tone.INFO -> MindMeshColors.InfoSoft to MindMeshColors.Info
        SaveStatusUi.Tone.WARNING -> MindMeshColors.WarningSoft to MindMeshColors.Warning
        SaveStatusUi.Tone.SUCCESS -> MindMeshColors.SuccessSoft to MindMeshColors.Success
        SaveStatusUi.Tone.DANGER -> MindMeshColors.DangerSoft to MindMeshColors.Danger
    }
    Column(Modifier.fillMaxWidth().padding(top = 12.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            StatusPill(status.label, container, color)
            Text(
                RelativeTime.format(System.currentTimeMillis(), item.createdAt),
                style = MaterialTheme.typography.bodySmall,
                color = MindMeshColors.InkMuted,
            )
        }
        Spacer(Modifier.height(6.dp))
        Text(item.url, style = MonoStyle, color = MindMeshColors.Ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
        Spacer(Modifier.height(4.dp))
        Text(item.message, style = MaterialTheme.typography.bodyMedium, color = MindMeshColors.InkMuted)
        if (SaveStatusUi.canRetry(item.state)) {
            Spacer(Modifier.height(8.dp))
            BrutButton(
                text = if (item.state == SaveStates.AUTH_ERROR) "Sign in again" else "Retry this save",
                style = BrutButtonStyle.SECONDARY,
                compact = true,
                onClick = onRetry,
            )
        }
    }
}
