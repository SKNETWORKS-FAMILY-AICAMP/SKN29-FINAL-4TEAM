package com.skn29.watercare.core.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

data class ReferenceDashboardPalette(
    val accent: Color,
    val accentSecondary: Color,
    val accentSoft: Color,
    val accentSoftSecondary: Color,
    val backgroundStart: Color,
    val backgroundEnd: Color,
    val textStrong: Color,
    val textMuted: Color,
    val success: Color,
    val warning: Color,
    val danger: Color,
)

val CustomerReferencePalette = ReferenceDashboardPalette(
    accent = Color(0xFF4E9BFF),
    accentSecondary = Color(0xFFA678FF),
    accentSoft = Color(0x334E9BFF),
    accentSoftSecondary = Color(0x2EA678FF),
    backgroundStart = Color(0xFFF8FCFF),
    backgroundEnd = Color(0xFFF7F4FF),
    textStrong = Color(0xFF12262B),
    textMuted = Color(0xFF61747C),
    success = Color(0xFF32BE9B),
    warning = Color(0xFFE2A141),
    danger = Color(0xFFE95570),
)

val TechnicianReferencePalette = ReferenceDashboardPalette(
    accent = Color(0xFF18B8A8),
    accentSecondary = Color(0xFF66D6C7),
    accentSoft = Color(0x3318B8A8),
    accentSoftSecondary = Color(0x2E66D6C7),
    backgroundStart = Color(0xFFF7FFFD),
    backgroundEnd = Color(0xFFF2FAFC),
    textStrong = Color(0xFF123136),
    textMuted = Color(0xFF5F777A),
    success = Color(0xFF18B8A8),
    warning = Color(0xFFE5A146),
    danger = Color(0xFFEA5B70),
)

data class ReferenceStatusItem(
    val icon: String,
    val label: String,
    val value: String,
    val healthy: Boolean = true,
)

data class ReferenceActionItem(
    val icon: String,
    val label: String,
    val subtitle: String = "",
    val enabled: Boolean = true,
    val testTag: String? = null,
    val onClick: () -> Unit,
)

data class ReferenceBottomItem(
    val icon: String,
    val label: String,
    val selected: Boolean = false,
    val onClick: () -> Unit = {},
)

@Composable
fun ReferenceDashboardHeader(
    roleLabel: String,
    palette: ReferenceDashboardPalette,
    onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        ReferencePill(
            text = "♙  $roleLabel ⌄",
            palette = palette,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ReferenceSquareIconButton(
                icon = "♢",
                palette = palette,
                onClick = onNotification,
            )
            ReferenceSquareIconButton(
                icon = "⌕",
                palette = palette,
                onClick = onSupport,
            )
        }
    }
}

@Composable
fun ReferenceHeroCard(
    greeting: String,
    subtitle: String,
    metricLabel: String,
    metricValue: String,
    metricUnit: String,
    progress: Float,
    footnote: String,
    imageRes: Int,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    ReferenceGlassPanel(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 278.dp),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(20.dp),
    ) {
        Box(
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth(0.62f)
                    .padding(vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    greeting,
                    color = palette.textStrong,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Black,
                )
                Text(
                    subtitle,
                    color = palette.textMuted,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(Modifier.height(12.dp))
                Text(
                    metricLabel,
                    color = palette.textMuted,
                    style = MaterialTheme.typography.bodySmall,
                )
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(
                        metricValue,
                        color = palette.textStrong,
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Black,
                    )
                    Text(
                        metricUnit,
                        modifier = Modifier.padding(start = 6.dp, bottom = 3.dp),
                        color = palette.textMuted,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                ReferenceProgressBar(
                    progress = progress,
                    palette = palette,
                )
                ReferencePill(
                    text = footnote,
                    palette = palette,
                )
            }

            Image(
                painter = painterResource(imageRes),
                contentDescription = null,
                modifier = Modifier
                    .align(Alignment.CenterEnd)
                    .fillMaxWidth(0.50f)
                    .fillMaxHeight(),
                contentScale = ContentScale.Fit,
            )
        }
    }
}

@Composable
fun ReferenceSectionHeader(
    title: String,
    trailing: String? = null,
    palette: ReferenceDashboardPalette,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            title,
            color = palette.textStrong,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Black,
        )
        if (!trailing.isNullOrBlank()) {
            Text(
                trailing,
                color = palette.textMuted,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
fun ReferenceStatusRow(
    items: List<ReferenceStatusItem>,
    palette: ReferenceDashboardPalette,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items.take(4).forEach { item ->
            ReferenceStatusTile(
                item = item,
                palette = palette,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
fun ReferenceActionRow(
    items: List<ReferenceActionItem>,
    palette: ReferenceDashboardPalette,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items.take(4).forEach { item ->
            ReferenceActionTile(
                item = item,
                palette = palette,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
fun ReferenceDetailCard(
    imageRes: Int,
    title: String,
    badge: String,
    lines: List<String>,
    status: String,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
    primaryActionLabel: String,
    secondaryActionLabel: String,
    onPrimaryAction: () -> Unit,
    onSecondaryAction: () -> Unit,
    timeline: List<String> = emptyList(),
    selectedTimelineIndex: Int = 0,
) {
    ReferenceGlassPanel(
        modifier = modifier.fillMaxWidth(),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(16.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ReferenceGlassImage(
                imageRes = imageRes,
                palette = palette,
                modifier = Modifier.size(94.dp),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(7.dp),
                ) {
                    Text(
                        title,
                        color = palette.textStrong,
                        fontWeight = FontWeight.Black,
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    ReferencePill(
                        text = badge,
                        palette = palette,
                    )
                }
                lines.forEach { line ->
                    Text(
                        line,
                        color = palette.textMuted,
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                ReferencePill(
                    text = status,
                    palette = palette,
                )
            }
        }

        if (timeline.isNotEmpty()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                timeline.forEachIndexed { index, label ->
                    Column(
                        modifier = Modifier.weight(1f),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Box(
                            modifier = Modifier
                                .size(10.dp)
                                .clip(CircleShape)
                                .background(
                                    if (index == selectedTimelineIndex) {
                                        palette.accent
                                    } else {
                                        Color(0xFFD8E2E7)
                                    }
                                )
                        )
                        Text(
                            label,
                            modifier = Modifier.padding(top = 4.dp),
                            color = if (index == selectedTimelineIndex) {
                                palette.accent
                            } else {
                                palette.textMuted
                            },
                            style = MaterialTheme.typography.labelSmall,
                            textAlign = TextAlign.Center,
                            maxLines = 1,
                        )
                    }
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            ReferenceGlassButton(
                text = primaryActionLabel,
                palette = palette,
                accent = true,
                onClick = onPrimaryAction,
                modifier = Modifier.weight(1f),
            )
            ReferenceGlassButton(
                text = secondaryActionLabel,
                palette = palette,
                onClick = onSecondaryAction,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
fun ReferenceBottomNavigation(
    items: List<ReferenceBottomItem>,
    palette: ReferenceDashboardPalette,
) {
    ReferenceGlassPanel(
        modifier = Modifier.fillMaxWidth(),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            items.take(5).forEach { item ->
                val interactionSource = remember { MutableInteractionSource() }
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(18.dp))
                        .clickable(
                            role = Role.Button,
                            interactionSource = interactionSource,
                            indication = null,
                            onClick = item.onClick,
                        )
                        .background(
                            if (item.selected) {
                                Brush.linearGradient(
                                    listOf(
                                        Color.White.copy(alpha = 0.78f),
                                        palette.accentSoft,
                                        palette.accentSoftSecondary,
                                    )
                                )
                            } else {
                                Brush.linearGradient(
                                    listOf(
                                        Color.Transparent,
                                        Color.Transparent,
                                    )
                                )
                            }
                        )
                        .padding(vertical = 9.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Text(
                        item.icon,
                        color = if (item.selected) {
                            palette.accent
                        } else {
                            palette.textMuted
                        },
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        item.label,
                        color = if (item.selected) {
                            palette.accent
                        } else {
                            palette.textMuted
                        },
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = if (item.selected) {
                            FontWeight.ExtraBold
                        } else {
                            FontWeight.Medium
                        },
                    )
                }
            }
        }
    }
}

@Composable
fun ReferenceGlassPanel(
    modifier: Modifier = Modifier,
    palette: ReferenceDashboardPalette,
    strong: Boolean = false,
    danger: Boolean = false,
    contentPadding: PaddingValues = PaddingValues(16.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = RoundedCornerShape(24.dp)
    val fillAlpha = if (strong) 0.74f else 0.56f
    val borderColor = if (danger) {
        palette.danger
    } else {
        Color.White.copy(alpha = 0.82f)
    }
    Column(
        modifier = modifier
            .shadow(
                elevation = if (danger) 5.dp else 12.dp,
                shape = shape,
                clip = false,
            )
            .clip(shape)
            .background(
                if (danger) {
                    Brush.linearGradient(
                        listOf(Color.White, Color.White)
                    )
                } else {
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = fillAlpha),
                            Color.White.copy(alpha = fillAlpha - 0.16f),
                            palette.accentSoftSecondary,
                        )
                    )
                }
            )
            .border(
                BorderStroke(
                    width = if (danger) 1.5.dp else 1.dp,
                    color = borderColor,
                ),
                shape,
            )
            .padding(contentPadding),
        verticalArrangement = Arrangement.spacedBy(11.dp),
        content = content,
    )
}

@Composable
fun ReferenceGlassButton(
    text: String,
    palette: ReferenceDashboardPalette,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    accent: Boolean = false,
) {
    val shape = RoundedCornerShape(18.dp)
    val interactionSource = remember { MutableInteractionSource() }
    Row(
        modifier = modifier
            .clip(shape)
            .clickable(
                enabled = enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick,
            )
            .background(
                if (accent) {
                    Brush.linearGradient(
                        listOf(
                            palette.accent,
                            palette.accentSecondary,
                        )
                    )
                } else {
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = 0.72f),
                            palette.accentSoft,
                        )
                    )
                }
            )
            .border(
                BorderStroke(
                    1.dp,
                    if (accent) {
                        Color.White.copy(alpha = 0.55f)
                    } else {
                        Color.White.copy(alpha = 0.84f)
                    },
                ),
                shape,
            )
            .heightIn(min = 48.dp)
            .padding(horizontal = 12.dp, vertical = 11.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text,
            color = if (accent) Color.White else palette.textStrong,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.ExtraBold,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun ReferenceSquareIconButton(
    icon: String,
    palette: ReferenceDashboardPalette,
    onClick: () -> Unit,
) {
    val shape = RoundedCornerShape(18.dp)
    val interactionSource = remember { MutableInteractionSource() }
    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(shape)
            .clickable(
                role = Role.Button,
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick,
            )
            .background(
                Brush.linearGradient(
                    listOf(
                        Color.White.copy(alpha = 0.78f),
                        palette.accentSoft,
                    )
                )
            )
            .border(
                BorderStroke(1.dp, Color.White.copy(alpha = 0.86f)),
                shape,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            icon,
            color = palette.textStrong,
            style = MaterialTheme.typography.titleLarge,
        )
    }
}

@Composable
private fun ReferenceStatusTile(
    item: ReferenceStatusItem,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    ReferenceGlassPanel(
        modifier = modifier.height(132.dp),
        palette = palette,
        contentPadding = PaddingValues(8.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                item.icon,
                style = MaterialTheme.typography.headlineSmall,
            )
            Text(
                item.label,
                color = palette.textMuted,
                style = MaterialTheme.typography.labelSmall,
                textAlign = TextAlign.Center,
                maxLines = 2,
            )
            Text(
                item.value,
                color = if (item.healthy) palette.accent else palette.danger,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (item.healthy) {
                Text(
                    "✓",
                    color = palette.success,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Black,
                )
            }
        }
    }
}

@Composable
private fun ReferenceActionTile(
    item: ReferenceActionItem,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val tagModifier = if (item.testTag.isNullOrBlank()) {
        Modifier
    } else {
        Modifier.testTag(item.testTag)
    }
    Column(
        modifier = modifier
            .then(tagModifier)
            .height(124.dp)
            .clip(RoundedCornerShape(22.dp))
            .clickable(
                enabled = item.enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = null,
                onClick = item.onClick,
            )
            .background(
                Brush.linearGradient(
                    listOf(
                        Color.White.copy(alpha = if (item.enabled) 0.76f else 0.42f),
                        if (item.enabled) {
                            palette.accentSoft
                        } else {
                            Color.Transparent
                        },
                    )
                )
            )
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = if (item.enabled) 0.86f else 0.42f),
                ),
                RoundedCornerShape(22.dp),
            )
            .padding(8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            item.icon,
            style = MaterialTheme.typography.headlineSmall,
        )
        Text(
            item.label,
            modifier = Modifier.padding(top = 5.dp),
            color = if (item.enabled) palette.textStrong else palette.textMuted,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.ExtraBold,
            textAlign = TextAlign.Center,
            maxLines = 2,
        )
        if (item.subtitle.isNotBlank()) {
            Text(
                item.subtitle,
                modifier = Modifier.padding(top = 2.dp),
                color = palette.textMuted,
                style = MaterialTheme.typography.labelSmall,
                textAlign = TextAlign.Center,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun ReferenceProgressBar(
    progress: Float,
    palette: ReferenceDashboardPalette,
) {
    val normalized = progress.coerceIn(0f, 1f)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(13.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(Color.White.copy(alpha = 0.65f))
            .border(
                BorderStroke(1.dp, Color.White.copy(alpha = 0.85f)),
                RoundedCornerShape(999.dp),
            ),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth(normalized)
                .fillMaxHeight()
                .clip(RoundedCornerShape(999.dp))
                .background(
                    Brush.horizontalGradient(
                        listOf(
                            palette.accent,
                            palette.accentSecondary,
                        )
                    )
                )
        )
    }
}

@Composable
private fun ReferencePill(
    text: String,
    palette: ReferenceDashboardPalette,
) {
    Text(
        text,
        modifier = Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(Color.White.copy(alpha = 0.68f))
            .border(
                BorderStroke(1.dp, Color.White.copy(alpha = 0.88f)),
                RoundedCornerShape(999.dp),
            )
            .padding(horizontal = 10.dp, vertical = 6.dp),
        color = palette.accent,
        style = MaterialTheme.typography.labelSmall,
        fontWeight = FontWeight.ExtraBold,
    )
}

@Composable
private fun ReferenceGlassImage(
    imageRes: Int,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(
                Brush.linearGradient(
                    listOf(
                        Color.White.copy(alpha = 0.78f),
                        palette.accentSoft,
                    )
                )
            )
            .border(
                BorderStroke(1.dp, Color.White.copy(alpha = 0.86f)),
                RoundedCornerShape(20.dp),
            )
            .padding(6.dp),
        contentAlignment = Alignment.Center,
    ) {
        Image(
            painter = painterResource(imageRes),
            contentDescription = null,
            modifier = Modifier.fillMaxWidth(),
            contentScale = ContentScale.Fit,
        )
    }
}
