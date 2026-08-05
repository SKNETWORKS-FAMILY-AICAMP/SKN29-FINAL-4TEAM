package com.skn29.watercare.core.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.ui.theme.Ink400
import com.skn29.watercare.core.ui.theme.Ink600
import com.skn29.watercare.core.ui.theme.Ink900
import com.skn29.watercare.core.ui.theme.Water500
import com.skn29.watercare.core.ui.theme.Water700
import com.skn29.watercare.core.ui.theme.WaterTokens

@Composable
fun LiquidGlassPanel(
    modifier: Modifier = Modifier,
    strong: Boolean = false,
    danger: Boolean = false,
    contentPadding: PaddingValues = PaddingValues(18.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = RoundedCornerShape(WaterTokens.RadiusCard)
    val baseFill = when {
        danger -> Color.White
        strong -> WaterTokens.GlassFillStrong
        else -> WaterTokens.GlassFill
    }
    val borderColor = if (danger) {
        WaterTokens.Danger
    } else {
        WaterTokens.GlassBorder
    }

    Column(
        modifier = modifier
            .shadow(
                elevation = if (danger) 4.dp else 10.dp,
                shape = shape,
                clip = false,
            )
            .clip(shape)
            .background(baseFill)
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        WaterTokens.GlassHighlight.copy(alpha = if (strong) 0.52f else 0.38f),
                        Color.Transparent,
                        WaterTokens.PearlLavender.copy(alpha = if (danger) 0f else 0.10f),
                    ),
                )
            )
            .border(
                BorderStroke(
                    width = if (danger) 1.5.dp else 1.dp,
                    color = borderColor,
                ),
                shape,
            )
            .padding(contentPadding),
        verticalArrangement = Arrangement.spacedBy(10.dp),
        content = content,
    )
}

@Composable
fun LiquidGlassButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    accent: Boolean = false,
    leadingIcon: String? = null,
) {
    val shape = RoundedCornerShape(WaterTokens.RadiusControl)
    val interactionSource = remember { MutableInteractionSource() }
    val fill = when {
        !enabled -> WaterTokens.GlassDisabled
        accent -> WaterTokens.GlassButtonStrong
        else -> WaterTokens.GlassButton
    }
    val borderColor = when {
        !enabled -> WaterTokens.GlassBorder.copy(alpha = 0.34f)
        accent -> WaterTokens.Water300.copy(alpha = 0.92f)
        else -> WaterTokens.GlassBorder
    }
    val textColor = when {
        !enabled -> Ink400
        accent -> Water700
        else -> Ink900
    }

    Row(
        modifier = modifier
            .shadow(6.dp, shape, clip = false)
            .clip(shape)
            .clickable(
                enabled = enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick,
            )
            .background(fill)
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        Color.White.copy(alpha = 0.58f),
                        WaterTokens.PearlBlue.copy(alpha = if (accent) 0.22f else 0.10f),
                        WaterTokens.PearlPink.copy(alpha = if (accent) 0.15f else 0.07f),
                    ),
                )
            )
            .border(BorderStroke(1.dp, borderColor), shape)
            .heightIn(min = 54.dp)
            .padding(horizontal = 18.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (!leadingIcon.isNullOrBlank()) {
            Text(
                leadingIcon,
                modifier = Modifier.padding(end = 8.dp),
                style = MaterialTheme.typography.titleMedium,
            )
        }
        Text(
            text,
            color = textColor,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
fun LiquidGlassActionCard(
    icon: String,
    title: String,
    subtitle: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val shape = RoundedCornerShape(WaterTokens.RadiusCard)
    val interactionSource = remember { MutableInteractionSource() }

    Column(
        modifier = modifier
            .shadow(8.dp, shape, clip = false)
            .clip(shape)
            .clickable(
                enabled = enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick,
            )
            .background(
                if (enabled) {
                    WaterTokens.GlassButtonStrong
                } else {
                    WaterTokens.GlassDisabled
                }
            )
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        Color.White.copy(alpha = 0.64f),
                        WaterTokens.PearlLavender.copy(alpha = if (enabled) 0.18f else 0.06f),
                        WaterTokens.PearlBlue.copy(alpha = if (enabled) 0.14f else 0.05f),
                    ),
                )
            )
            .border(
                BorderStroke(
                    1.dp,
                    if (enabled) WaterTokens.GlassBorder else WaterTokens.GlassBorder.copy(alpha = 0.35f),
                ),
                shape,
            )
            .padding(15.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            icon,
            style = MaterialTheme.typography.headlineSmall,
        )
        Text(
            title,
            color = if (enabled) Ink900 else Ink400,
            fontWeight = FontWeight.ExtraBold,
            style = MaterialTheme.typography.titleSmall,
        )
        Text(
            subtitle,
            color = if (enabled) Ink600 else Ink400,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
fun LiquidGlassMetricTile(
    value: String,
    label: String,
    modifier: Modifier = Modifier,
    tint: Color = Water500,
) {
    val shape = RoundedCornerShape(WaterTokens.RadiusControl)

    Column(
        modifier = modifier
            .clip(shape)
            .background(WaterTokens.GlassButton)
            .background(
                Brush.linearGradient(
                    listOf(
                        Color.White.copy(alpha = 0.52f),
                        tint.copy(alpha = 0.10f),
                    )
                )
            )
            .border(BorderStroke(1.dp, WaterTokens.GlassBorder), shape)
            .padding(13.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            value,
            color = tint,
            fontWeight = FontWeight.ExtraBold,
            style = MaterialTheme.typography.titleMedium,
        )
        Text(
            label,
            color = Ink600,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
fun LiquidGlassPill(
    text: String,
    modifier: Modifier = Modifier,
    tint: Color = Water500,
) {
    val shape = RoundedCornerShape(WaterTokens.RadiusPill)

    Text(
        text = text,
        modifier = modifier
            .clip(shape)
            .background(Color.White.copy(alpha = 0.48f))
            .background(tint.copy(alpha = 0.10f))
            .border(
                BorderStroke(1.dp, tint.copy(alpha = 0.30f)),
                shape,
            )
            .padding(horizontal = 11.dp, vertical = 6.dp),
        color = tint,
        fontWeight = FontWeight.Bold,
        style = MaterialTheme.typography.bodySmall,
    )
}
