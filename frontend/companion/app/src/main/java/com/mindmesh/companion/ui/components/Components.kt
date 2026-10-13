package com.mindmesh.companion.ui.components

import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import com.mindmesh.companion.R
import com.mindmesh.companion.ui.theme.MindMeshColors
import com.mindmesh.companion.ui.theme.MonoStyle

private val CardShape = RoundedCornerShape(14.dp)
private val ControlShape = RoundedCornerShape(12.dp)
private val PillShape = RoundedCornerShape(50)

/** Sheet with the website's hard ink border and offset shadow. */
@Composable
fun BrutCard(
    modifier: Modifier = Modifier,
    shadow: Dp = 4.dp,
    background: Color = MindMeshColors.Sheet,
    contentPadding: PaddingValues = PaddingValues(18.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    Box(modifier = modifier) {
        if (shadow > 0.dp) {
            Box(
                Modifier
                    .matchParentSize()
                    .padding(start = shadow, top = shadow)
                    .background(MindMeshColors.Ink, CardShape),
            )
        }
        Column(
            Modifier
                .background(background, CardShape)
                .border(2.dp, MindMeshColors.Ink, CardShape)
                .padding(contentPadding),
            content = content,
        )
    }
}

enum class BrutButtonStyle { PRIMARY, SECONDARY, GHOST }

/** A two-position theme control sized to stay clear of adjacent account actions. */
@Composable
fun ThemeToggle(
    darkTheme: Boolean,
    onToggle: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val thumbOffset by animateDpAsState(if (darkTheme) 72.dp else 2.dp, label = "themeThumb")
    val track = if (darkTheme) MindMeshColors.Ink else MindMeshColors.PaperCard
    val inactive = if (darkTheme) MindMeshColors.PaperCard else MindMeshColors.InkMuted
    val thumb = if (darkTheme) MindMeshColors.PaperCard else MindMeshColors.Ink
    val thumbText = if (darkTheme) MindMeshColors.Ink else MindMeshColors.PaperCard

    Box(
        modifier
            .width(136.dp)
            .height(48.dp),
    ) {
        Box(
            Modifier
                .matchParentSize()
                .padding(start = 4.dp, top = 4.dp)
                .background(MindMeshColors.Ink, ControlShape),
        )
        Box(
            Modifier
                .matchParentSize()
                .background(track, ControlShape)
                .border(2.dp, MindMeshColors.Ink, ControlShape)
                .clickable(onClick = onToggle),
        ) {
            Box(
                Modifier
                    .align(Alignment.CenterStart)
                    .offset(x = thumbOffset)
                    .width(62.dp)
                    .fillMaxHeight()
                    .padding(4.dp)
                    .background(thumb, RoundedCornerShape(9.dp)),
            )
            Text(
                "Light",
                style = MaterialTheme.typography.labelMedium,
                color = if (darkTheme) inactive else thumbText,
                modifier = Modifier.align(Alignment.CenterStart).padding(start = 12.dp),
            )
            Text(
                "Dark",
                style = MaterialTheme.typography.labelMedium,
                color = if (darkTheme) thumbText else inactive,
                modifier = Modifier.align(Alignment.CenterEnd).padding(end = 12.dp),
            )
        }
    }
}

/** Pressable button that sinks into its hard shadow, like the website's brut-btn. */
@Composable
fun BrutButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    loading: Boolean = false,
    style: BrutButtonStyle = BrutButtonStyle.PRIMARY,
    compact: Boolean = false,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val active = enabled && !loading
    val shadow by animateDpAsState(if (pressed && active) 0.dp else 4.dp, label = "brutShadow")
    val background = when (style) {
        BrutButtonStyle.PRIMARY -> MindMeshColors.Orange
        BrutButtonStyle.SECONDARY -> MindMeshColors.Sheet
        BrutButtonStyle.GHOST -> Color.Transparent
    }
    val contentColor = MindMeshColors.Ink

    Box(modifier = modifier) {
        if (shadow > 0.dp && style != BrutButtonStyle.GHOST) {
            Box(
                Modifier
                    .matchParentSize()
                    .padding(start = shadow, top = shadow)
                    .background(MindMeshColors.Ink, ControlShape),
            )
        }
        Row(
            Modifier
                .then(if (compact) Modifier else Modifier.fillMaxWidth())
                .then(if (style == BrutButtonStyle.GHOST) Modifier else Modifier.background(background, ControlShape).border(2.dp, MindMeshColors.Ink, ControlShape))
                .clickable(interactionSource = interactionSource, indication = null, enabled = active, onClick = onClick)
                .padding(horizontal = 16.dp, vertical = 13.dp)
                .alpha(if (enabled) 1f else 0.45f),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (loading) {
                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = contentColor)
                Spacer(Modifier.width(10.dp))
            }
            Text(
                text = text,
                style = MaterialTheme.typography.labelLarge,
                color = contentColor,
                maxLines = 1,
            )
        }
    }
}

/** Bordered text field in the website's ink style. */
@Composable
fun BrutTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    singleLine: Boolean = true,
    keyboardType: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction = ImeAction.Next,
    onImeAction: (() -> Unit)? = null,
    supportingText: String? = null,
    isError: Boolean = false,
    trailingIcon: (@Composable () -> Unit)? = null,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label, style = MaterialTheme.typography.labelMedium) },
        modifier = modifier.fillMaxWidth(),
        enabled = enabled,
        singleLine = singleLine,
        isError = isError,
        textStyle = MaterialTheme.typography.bodyLarge,
        shape = ControlShape,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType, imeAction = imeAction),
        keyboardActions = KeyboardActions(
            onNext = { onImeAction?.invoke() },
            onDone = { onImeAction?.invoke() },
            onGo = { onImeAction?.invoke() },
        ),
        trailingIcon = trailingIcon,
        supportingText = supportingText?.let { { Text(it, style = MaterialTheme.typography.bodySmall) } },
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = MindMeshColors.Ink,
            unfocusedBorderColor = MindMeshColors.Ink,
            disabledBorderColor = MindMeshColors.Ink.copy(alpha = 0.4f),
            errorBorderColor = MindMeshColors.Danger,
            focusedContainerColor = MindMeshColors.Sheet,
            unfocusedContainerColor = MindMeshColors.Sheet,
            disabledContainerColor = MindMeshColors.PaperAlt,
            focusedTextColor = MindMeshColors.Ink,
            unfocusedTextColor = MindMeshColors.Ink,
            disabledTextColor = MindMeshColors.InkMuted,
            cursorColor = MindMeshColors.Orange,
            focusedLabelColor = MindMeshColors.Ink,
            unfocusedLabelColor = MindMeshColors.InkMuted,
            focusedTrailingIconColor = MindMeshColors.Ink,
            unfocusedTrailingIconColor = MindMeshColors.InkMuted,
        ),
    )
}

/** Compact uppercase status chip with a monospace label. */
@Composable
fun StatusPill(text: String, container: Color, contentColor: Color, modifier: Modifier = Modifier) {
    Box(
        modifier
            .background(container, PillShape)
            .border(1.5.dp, MindMeshColors.Ink, PillShape)
            .padding(horizontal = 10.dp, vertical = 3.dp),
    ) {
        Text(text.uppercase(), style = MonoStyle.copy(fontSize = 11.sp), color = contentColor, maxLines = 1)
    }
}

/** Banner for one-shot messages: info, success, warning or error. */
@Composable
fun NoticeBanner(
    kind: com.mindmesh.companion.UiNotice.Kind,
    text: String,
    onDismiss: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    val (container, accent) = when (kind) {
        com.mindmesh.companion.UiNotice.Kind.INFO -> MindMeshColors.InfoSoft to MindMeshColors.Info
        com.mindmesh.companion.UiNotice.Kind.SUCCESS -> MindMeshColors.SuccessSoft to MindMeshColors.Success
        com.mindmesh.companion.UiNotice.Kind.WARNING -> MindMeshColors.WarningSoft to MindMeshColors.Warning
        com.mindmesh.companion.UiNotice.Kind.ERROR -> MindMeshColors.DangerSoft to MindMeshColors.Danger
    }
    Row(
        modifier
            .fillMaxWidth()
            .background(container, ControlShape)
            .border(2.dp, MindMeshColors.Ink, ControlShape)
            .padding(start = 12.dp, top = 10.dp, end = 4.dp, bottom = 10.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Box(
            Modifier
                .padding(top = 4.dp, end = 10.dp)
                .size(10.dp)
                .background(accent, RoundedCornerShape(2.dp)),
        )
        Text(
            text,
            style = MaterialTheme.typography.bodyMedium,
            color = MindMeshColors.Ink,
            modifier = Modifier.weight(1f),
        )
        if (onDismiss != null) {
            IconButton(onClick = onDismiss, modifier = Modifier.size(32.dp)) {
                Icon(Icons.Filled.Close, contentDescription = "Dismiss", tint = MindMeshColors.Ink)
            }
        }
    }
}

/** Logo tile + wordmark, identical to the website header treatment. */
@Composable
fun BrandHeader(modifier: Modifier = Modifier, subtitle: String? = null) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Image(
            painter = painterResource(R.drawable.logo_mindmesh),
            contentDescription = "MindMesh",
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .size(46.dp)
                .clip(RoundedCornerShape(11.dp)),
        )
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(
                "MindMesh",
                style = MaterialTheme.typography.titleLarge,
                color = MindMeshColors.Ink,
                fontWeight = FontWeight.Black,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (subtitle != null) {
                Text(subtitle, style = MaterialTheme.typography.labelMedium, color = MindMeshColors.InkMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

/** Orange eyebrow used above screen titles, matching the website's mono labels. */
@Composable
fun Eyebrow(text: String, modifier: Modifier = Modifier, color: Color = MindMeshColors.Ink) {
    Text(
        text.uppercase(),
        style = MonoStyle.copy(fontWeight = FontWeight.Bold, fontSize = 11.sp, letterSpacing = 1.4.sp),
        color = color,
        modifier = modifier,
    )
}
