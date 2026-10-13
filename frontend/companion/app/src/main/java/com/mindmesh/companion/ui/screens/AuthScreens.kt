package com.mindmesh.companion.ui.screens

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import com.mindmesh.companion.MainViewModel
import com.mindmesh.companion.R
import com.mindmesh.companion.UiNotice
import com.mindmesh.companion.auth.SupabaseAuth
import com.mindmesh.companion.ui.components.BrandHeader
import com.mindmesh.companion.ui.components.BrutButton
import com.mindmesh.companion.ui.components.BrutButtonStyle
import com.mindmesh.companion.ui.components.BrutCard
import com.mindmesh.companion.ui.components.BrutTextField
import com.mindmesh.companion.ui.components.Eyebrow
import com.mindmesh.companion.ui.components.NoticeBanner
import com.mindmesh.companion.ui.components.StatusPill
import com.mindmesh.companion.ui.theme.MindMeshColors
import com.mindmesh.companion.ui.theme.MonoStyle

/** Shared print-brutalism frame for every unauthenticated screen. */
@Composable
private fun AuthScaffold(
    eyebrow: String,
    title: String,
    subtitle: String,
    notice: UiNotice?,
    onDismissNotice: () -> Unit,
    pendingLink: String?,
    footer: @Composable () -> Unit,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        Modifier
            .fillMaxSize()
            .background(MindMeshColors.Paper)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 22.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        BrandHeader(Modifier.fillMaxWidth())
        Spacer(Modifier.height(18.dp))
        if (notice != null) {
            NoticeBanner(notice.kind, notice.text, onDismiss = onDismissNotice, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(14.dp))
        }
        BrutCard(Modifier.fillMaxWidth()) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(MindMeshColors.Orange, RoundedCornerShape(10.dp))
                    .border(2.dp, MindMeshColors.Ink, RoundedCornerShape(10.dp))
                    .padding(16.dp),
            ) {
                Eyebrow(eyebrow)
                Spacer(Modifier.height(8.dp))
                Text(title, style = MaterialTheme.typography.headlineMedium, color = MindMeshColors.Ink)
                Spacer(Modifier.height(6.dp))
                Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MindMeshColors.Ink)
            }
            Spacer(Modifier.height(18.dp))
            content()
            Spacer(Modifier.height(16.dp))
            footer()
        }
        if (pendingLink != null) {
            Spacer(Modifier.height(16.dp))
            BrutCard(Modifier.fillMaxWidth(), background = MindMeshColors.PaperAlt, contentPadding = PaddingValues(14.dp)) {
                Eyebrow("Shared link waiting")
                Spacer(Modifier.height(6.dp))
                Text(pendingLink, style = MonoStyle, color = MindMeshColors.Ink, maxLines = 2)
                Spacer(Modifier.height(4.dp))
                Text(
                    "Sign in and this link is ready to save to MindMesh.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MindMeshColors.InkMuted,
                )
            }
        }
        Spacer(Modifier.height(26.dp))
    }
}

private fun googleSignIn(context: Context, vm: MainViewModel) {
    val intent = runCatching { SupabaseAuth.googleIntent(context) }.getOrElse { error ->
        vm.setNotice(UiNotice.Kind.ERROR, error.message ?: "Google sign-in is not configured for this build.")
        return
    }
    runCatching { context.startActivity(intent) }
        .onFailure { vm.setNotice(UiNotice.Kind.ERROR, "Could not open the browser for Google sign-in.") }
}

@Composable
fun WelcomeScreen(vm: MainViewModel) {
    val context = LocalContext.current
    val notice by vm.notice.collectAsState()
    val draft by vm.draftUrl.collectAsState()

    AuthScaffold(
        eyebrow = "Your personal workspace",
        title = "Your knowledge. Connected.",
        subtitle = "Save sources from any app, then ask questions across your library on MindMesh.",
        notice = notice,
        onDismissNotice = vm::dismissNotice,
        pendingLink = draft.ifBlank { null },
        footer = {
            Text(
                "Your library belongs to your account. Every save you make here reports its own status.",
                style = MaterialTheme.typography.bodySmall,
                color = MindMeshColors.InkMuted,
            )
        },
    ) {
        BrutButton("Sign in", onClick = { vm.navigate(com.mindmesh.companion.Screen.LOGIN) })
        Spacer(Modifier.height(10.dp))
        BrutButton("Create account", style = BrutButtonStyle.SECONDARY, onClick = { vm.navigate(com.mindmesh.companion.Screen.SIGNUP) })
        Spacer(Modifier.height(10.dp))
        BrutButton("Continue with Google", style = BrutButtonStyle.SECONDARY, onClick = { googleSignIn(context, vm) })
    }
}

@Composable
fun LoginScreen(vm: MainViewModel) {
    val context = LocalContext.current
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    val busy by vm.busy.collectAsState()
    val notice by vm.notice.collectAsState()
    val draft by vm.draftUrl.collectAsState()
    val passwordFocus = remember { FocusRequester() }

    AuthScaffold(
        eyebrow = "Sign in",
        title = "Welcome back.",
        subtitle = "Pick up where you left off — your saves sync as soon as you are in.",
        notice = notice,
        onDismissNotice = vm::dismissNotice,
        pendingLink = draft.ifBlank { null },
        footer = {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                Text("New to MindMesh?", style = MaterialTheme.typography.bodyMedium, color = MindMeshColors.InkMuted)
                Spacer(Modifier.height(0.dp))
                Text(
                    " Create account",
                    style = MaterialTheme.typography.labelLarge,
                    color = MindMeshColors.Ink,
                    textDecoration = TextDecoration.Underline,
                    modifier = Modifier.clickable(enabled = !busy) { vm.navigate(com.mindmesh.companion.Screen.SIGNUP) },
                )
            }
        },
    ) {
        BrutTextField(
            value = email,
            onValueChange = { email = it },
            label = "Email",
            enabled = !busy,
            keyboardType = KeyboardType.Email,
            imeAction = ImeAction.Next,
            onImeAction = { passwordFocus.requestFocus() },
        )
        Spacer(Modifier.height(12.dp))
        BrutTextField(
            value = password,
            onValueChange = { password = it },
            label = "Password",
            enabled = !busy,
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Done,
            onImeAction = { vm.signIn(email, password) },
        )
        Spacer(Modifier.height(4.dp))
        Text(
            "Forgot password? Tap here and we will email you a reset link.",
            style = MaterialTheme.typography.bodySmall,
            color = MindMeshColors.InkMuted,
            modifier = Modifier
                .focusRequester(passwordFocus)
                .clickable(enabled = !busy) { vm.sendPasswordReset(email) },
        )
        Spacer(Modifier.height(16.dp))
        BrutButton("Sign in", onClick = { vm.signIn(email, password) }, enabled = !busy, loading = busy)
        Spacer(Modifier.height(10.dp))
        BrutButton("Continue with Google", style = BrutButtonStyle.SECONDARY, enabled = !busy, onClick = { googleSignIn(context, vm) })
    }
}

@Composable
fun SignupScreen(vm: MainViewModel) {
    val context = LocalContext.current
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var confirm by rememberSaveable { mutableStateOf("") }
    val busy by vm.busy.collectAsState()
    val notice by vm.notice.collectAsState()
    val draft by vm.draftUrl.collectAsState()

    AuthScaffold(
        eyebrow = "Create account",
        title = "Your knowledge. Connected.",
        subtitle = "Start with your email and a secure password — the same account works on the website.",
        notice = notice,
        onDismissNotice = vm::dismissNotice,
        pendingLink = draft.ifBlank { null },
        footer = {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                Text("Already have an account?", style = MaterialTheme.typography.bodyMedium, color = MindMeshColors.InkMuted)
                Text(
                    " Sign in",
                    style = MaterialTheme.typography.labelLarge,
                    color = MindMeshColors.Ink,
                    textDecoration = TextDecoration.Underline,
                    modifier = Modifier.clickable(enabled = !busy) { vm.navigate(com.mindmesh.companion.Screen.LOGIN) },
                )
            }
        },
    ) {
        BrutTextField(
            value = email,
            onValueChange = { email = it },
            label = "Email",
            enabled = !busy,
            keyboardType = KeyboardType.Email,
        )
        Spacer(Modifier.height(12.dp))
        BrutTextField(
            value = password,
            onValueChange = { password = it },
            label = "Password (8+ characters)",
            enabled = !busy,
            keyboardType = KeyboardType.Password,
        )
        Spacer(Modifier.height(12.dp))
        BrutTextField(
            value = confirm,
            onValueChange = { confirm = it },
            label = "Confirm password",
            enabled = !busy,
            keyboardType = KeyboardType.Password,
            imeAction = ImeAction.Done,
            onImeAction = { vm.signUp(email, password, confirm) },
        )
        Spacer(Modifier.height(16.dp))
        BrutButton("Create account", onClick = { vm.signUp(email, password, confirm) }, enabled = !busy, loading = busy)
        Spacer(Modifier.height(10.dp))
        BrutButton("Continue with Google", style = BrutButtonStyle.SECONDARY, enabled = !busy, onClick = { googleSignIn(context, vm) })
    }
}

@Composable
fun VerifyScreen(vm: MainViewModel) {
    val email by vm.verifyEmail.collectAsState()
    val busy by vm.busy.collectAsState()
    val notice by vm.notice.collectAsState()

    AuthScaffold(
        eyebrow = "One more step",
        title = "Confirm your email.",
        subtitle = if (email.isBlank()) "Open the confirmation link we just emailed you."
        else "We sent a confirmation link to $email. Open it, then sign in here.",
        notice = notice,
        onDismissNotice = vm::dismissNotice,
        pendingLink = null,
        footer = {
            Text(
                "Did not get it? Check spam, or resend — the link opens on this device.",
                style = MaterialTheme.typography.bodySmall,
                color = MindMeshColors.InkMuted,
            )
        },
    ) {
        StatusPill("Awaiting confirmation", MindMeshColors.WarningSoft, MindMeshColors.Warning)
        Spacer(Modifier.height(14.dp))
        BrutButton("I've confirmed — go to sign in", onClick = { vm.navigate(com.mindmesh.companion.Screen.LOGIN) }, enabled = !busy)
        Spacer(Modifier.height(10.dp))
        BrutButton("Resend confirmation email", style = BrutButtonStyle.SECONDARY, onClick = vm::resendConfirmation, enabled = !busy, loading = busy)
        Spacer(Modifier.height(10.dp))
        BrutButton("Use a different email", style = BrutButtonStyle.GHOST, onClick = { vm.navigate(com.mindmesh.companion.Screen.SIGNUP) }, enabled = !busy)
    }
}

/** Shown while a stored session is being verified against Supabase. */
@Composable
fun SplashScreen(subtitle: String) {
    Box(Modifier.fillMaxSize().background(MindMeshColors.Paper), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            ImageLogo(96.dp)
            Spacer(Modifier.height(14.dp))
            Text("MindMesh", style = MaterialTheme.typography.headlineMedium, color = MindMeshColors.Ink, fontWeight = FontWeight.Black)
            Spacer(Modifier.height(10.dp))
            Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MindMeshColors.InkMuted)
            Spacer(Modifier.height(18.dp))
            CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp, color = MindMeshColors.Orange)
        }
    }
}

@Composable
private fun ImageLogo(size: androidx.compose.ui.unit.Dp) {
    androidx.compose.foundation.Image(
        painter = painterResource(R.drawable.logo_mindmesh),
        contentDescription = null,
        modifier = Modifier.size(size).clip(RoundedCornerShape(size * 0.22f)),
    )
}
