package com.mindmesh.companion.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Print-brutalism palette, mirrored from the MindMesh website (frontend/app/globals.css). */
object MindMeshColors {
    private val darkMode = mutableStateOf(false)
    internal fun applyMode(isDark: Boolean) { darkMode.value = isDark }
    val Paper get() = if (darkMode.value) Color(0xFF15110F) else Color(0xFFFFF6E9)
    val PaperAlt get() = if (darkMode.value) Color(0xFF211914) else Color(0xFFF7EBDC)
    val PaperCard get() = if (darkMode.value) Color(0xFF32261F) else Color(0xFFEEE0CA)
    val Ink get() = if (darkMode.value) Color(0xFFFFF6E9) else Color(0xFF111111)
    val InkMuted get() = if (darkMode.value) Color(0xFFE6D1BE) else Color(0xFF5E4837)
    val Orange = Color(0xFFFF5A00)
    val OrangeHover = Color(0xFFE34B00)
    val Sheet get() = if (darkMode.value) Color(0xFF211914) else Color(0xFFFFFFFF)
    val Success = Color(0xFF168A4A)
    val SuccessSoft = Color(0xFFE4F3E9)
    val Warning = Color(0xFFB96A00)
    val WarningSoft = Color(0xFFFFEFD6)
    val Danger = Color(0xFFC62828)
    val DangerSoft = Color(0xFFFBE2E2)
    val Info = Color(0xFF087EA4)
    val InfoSoft = Color(0xFFE1F1F7)
}

private val Display = TextStyle(
    fontFamily = FontFamily.SansSerif,
    fontWeight = FontWeight.Black,
    fontSize = 30.sp,
    lineHeight = 34.sp,
    letterSpacing = (-0.5).sp,
)

private val AppTypography = Typography(
    headlineLarge = Display,
    headlineMedium = Display.copy(fontSize = 24.sp, lineHeight = 28.sp),
    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 20.sp, lineHeight = 24.sp, letterSpacing = (-0.2).sp),
    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 16.sp, lineHeight = 20.sp),
    titleSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 14.sp, lineHeight = 18.sp),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 16.sp, lineHeight = 22.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 14.sp, lineHeight = 19.sp),
    bodySmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Normal, fontSize = 12.sp, lineHeight = 16.sp),
    labelLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Black, fontSize = 14.sp, lineHeight = 18.sp, letterSpacing = 0.7.sp),
    labelMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 12.sp, lineHeight = 16.sp, letterSpacing = 0.5.sp),
    labelSmall = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, fontSize = 11.sp, lineHeight = 14.sp, letterSpacing = 0.6.sp),
)

/** Monospace style for URLs, ids and status codes. */
val MonoStyle = TextStyle(
    fontFamily = FontFamily.Monospace,
    fontWeight = FontWeight.Medium,
    fontSize = 13.sp,
    lineHeight = 17.sp,
)

@Composable
fun MindMeshTheme(darkTheme: Boolean = false, content: @Composable () -> Unit) {
    SideEffect { MindMeshColors.applyMode(darkTheme) }
    MaterialTheme(
        colorScheme = if (darkTheme) darkColorScheme(
            primary = MindMeshColors.Orange, onPrimary = MindMeshColors.Ink,
            background = Color(0xFF15110F), onBackground = Color(0xFFFFF6E9),
            surface = Color(0xFF211914), onSurface = Color(0xFFFFF6E9),
            surfaceVariant = Color(0xFF32261F), onSurfaceVariant = Color(0xFFE6D1BE),
            outline = Color(0xFFFFF6E9), error = MindMeshColors.Danger,
        ) else lightColorScheme(
            primary = MindMeshColors.Orange,
            onPrimary = MindMeshColors.Ink,
            primaryContainer = MindMeshColors.Orange,
            onPrimaryContainer = MindMeshColors.Ink,
            secondary = MindMeshColors.Ink,
            onSecondary = MindMeshColors.Sheet,
            background = MindMeshColors.Paper,
            onBackground = MindMeshColors.Ink,
            surface = MindMeshColors.Sheet,
            onSurface = MindMeshColors.Ink,
            surfaceVariant = MindMeshColors.PaperAlt,
            onSurfaceVariant = MindMeshColors.InkMuted,
            surfaceContainerLowest = MindMeshColors.Sheet,
            surfaceContainerLow = MindMeshColors.PaperAlt,
            outline = MindMeshColors.Ink,
            outlineVariant = MindMeshColors.PaperCard,
            error = MindMeshColors.Danger,
            onError = MindMeshColors.Sheet,
            errorContainer = MindMeshColors.DangerSoft,
            onErrorContainer = MindMeshColors.Danger,
        ),
        typography = AppTypography,
        shapes = androidx.compose.material3.Shapes(
            small = RoundedCornerShape(10.dp),
            medium = RoundedCornerShape(14.dp),
            large = RoundedCornerShape(18.dp),
        ),
        content = content,
    )
}
