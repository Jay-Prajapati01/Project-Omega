package com.mindmesh.companion.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import com.mindmesh.companion.AuthUiState
import com.mindmesh.companion.MainViewModel
import com.mindmesh.companion.Screen
import com.mindmesh.companion.ui.screens.HomeScreen
import com.mindmesh.companion.ui.screens.LoginScreen
import com.mindmesh.companion.ui.screens.SignupScreen
import com.mindmesh.companion.ui.screens.SplashScreen
import com.mindmesh.companion.ui.screens.VerifyScreen
import com.mindmesh.companion.ui.screens.WelcomeScreen

/**
 * Root of the companion: a tiny state machine over Welcome / Login / Signup /
 * Verify / Home, driven entirely by [MainViewModel].
 */
@Composable
fun MindMeshApp(viewModel: MainViewModel) {
    val screen by viewModel.screen.collectAsState()
    val auth by viewModel.auth.collectAsState()
    val darkTheme by viewModel.darkTheme.collectAsState()

    if (auth is AuthUiState.Restoring) {
        SplashScreen("Checking your MindMesh session…")
        return
    }

    when (screen) {
        Screen.WELCOME -> WelcomeScreen(viewModel)
        Screen.LOGIN -> LoginScreen(viewModel)
        Screen.SIGNUP -> SignupScreen(viewModel)
        Screen.VERIFY -> VerifyScreen(viewModel)
        Screen.HOME -> HomeScreen(viewModel, darkTheme)
    }
}
