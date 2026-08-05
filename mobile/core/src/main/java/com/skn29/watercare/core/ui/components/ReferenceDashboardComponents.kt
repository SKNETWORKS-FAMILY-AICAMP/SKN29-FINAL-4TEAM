package com.skn29.watercare.core.ui.components

import androidx.annotation.DrawableRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

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
    @DrawableRes val iconRes: Int,
    val label: String,
    val value: String,
    val healthy: Boolean = true,
)

data class ReferenceActionItem(
    @DrawableRes val iconRes: Int,
    val label: String,
    val subtitle: String = "",
    val enabled: Boolean = true,
    val testTag: String? = null,
    val onClick: () -> Unit,
)

data class ReferenceBottomItem(
    @DrawableRes val iconRes: Int,
    val label: String,
    val selected: Boolean = false,
    val onClick: () -> Unit = {},
)

@Composable
fun ReferenceDashboardScaffold(
    title: String,
    roleLabel: String,
    palette: ReferenceDashboardPalette,
    bottomItems: List<ReferenceBottomItem> = emptyList(),
    modifier: Modifier = Modifier,
    onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
    content: @Composable ColumnScope.() -> Unit,
) {
    ReferencePearlBackground(
        palette = palette,
        modifier = modifier,
    ) {
        Scaffold(
            containerColor = Color.Transparent,
            bottomBar = {
                if (bottomItems.isNotEmpty()) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .navigationBarsPadding()
                            .padding(
                                start = 14.dp,
                                end = 14.dp,
                                bottom = 8.dp,
                            ),
                    ) {
                        ReferenceBottomNavigation(
                            items = bottomItems,
                            palette = palette,
                        )
                    }
                }
            },
        ) { innerPadding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .verticalScroll(rememberScrollState())
                    .padding(
                        start = 16.dp,
                        end = 16.dp,
                        top = 14.dp,
                        bottom = 18.dp,
                    ),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                Text(
                    title,
                    color = palette.textStrong,
                    fontSize = 32.sp,
                    lineHeight = 38.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = (-1.3).sp,
                )
                ReferenceDashboardHeader(
                    roleLabel = roleLabel,
                    palette = palette,
                    onNotification = onNotification,
                    onSupport = onSupport,
                )
                content()
            }
        }
    }
}

@Composable
fun ReferenceWelcomeCard(
    title: String,
    subtitle: String,
    @DrawableRes imageRes: Int,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    ReferenceGlassPanel(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 224.dp),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(18.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(190.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth(0.58f)
                    .align(Alignment.CenterStart),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text(
                    title,
                    color = palette.textStrong,
                    fontSize = 29.sp,
                    lineHeight = 35.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = (-0.8).sp,
                )
                Text(
                    subtitle,
                    color = palette.textMuted,
                    style = MaterialTheme.typography.bodyMedium,
                    lineHeight = 24.sp,
                )
            }
            Image(
                painter = painterResource(imageRes),
                contentDescription = null,
                modifier = Modifier
                    .size(176.dp)
                    .align(Alignment.CenterEnd)
                    .graphicsLayer {
                        translationX = 16.dp.toPx()
                    },
                contentScale = ContentScale.Fit,
            )
        }
    }
}

@Composable
fun ReferenceCompactBanner(
    title: String,
    message: String,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
    warning: Boolean = false,
    actionLabel: String? = null,
    onAction: () -> Unit = {},
) {
    ReferenceGlassPanel(
        modifier = modifier.fillMaxWidth(),
        palette = palette,
        danger = false,
        contentPadding = PaddingValues(
            horizontal = 16.dp,
            vertical = 14.dp,
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(11.dp)
                    .clip(CircleShape)
                    .background(
                        if (warning) {
                            palette.warning
                        } else {
                            palette.success
                        }
                    )
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Text(
                    title,
                    color = if (warning) {
                        palette.warning
                    } else {
                        palette.accent
                    },
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.ExtraBold,
                )
                Text(
                    message,
                    color = palette.textMuted,
                    style = MaterialTheme.typography.bodySmall,
                    lineHeight = 19.sp,
                )
            }
            if (!actionLabel.isNullOrBlank()) {
                ReferenceGlassButton(
                    text = actionLabel,
                    palette = palette,
                    onClick = onAction,
                    compact = true,
                )
            }
        }
    }
}

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
        Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            ReferenceSquareIconButton(
                symbol = "♢",
                palette = palette,
                onClick = onNotification,
            )
            ReferenceSquareIconButton(
                symbol = "⌕",
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
    @DrawableRes imageRes: Int,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    ReferenceGlassPanel(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = 246.dp),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(18.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(210.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(190.dp)
                    .align(Alignment.BottomEnd)
                    .clip(CircleShape)
                    .background(
                        Brush.radialGradient(
                            listOf(
                                Color.White.copy(alpha = 0.86f),
                                palette.accentSoft,
                                Color.Transparent,
                            )
                        )
                    )
            )
            Column(
                modifier = Modifier
                    .fillMaxWidth(0.61f)
                    .align(Alignment.CenterStart),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    greeting,
                    color = palette.textStrong,
                    fontSize = 25.sp,
                    lineHeight = 31.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = (-0.6).sp,
                )
                Text(
                    subtitle,
                    color = palette.textMuted,
                    style = MaterialTheme.typography.bodySmall,
                    lineHeight = 20.sp,
                )
                Spacer(Modifier.height(7.dp))
                Text(
                    metricLabel,
                    color = palette.textMuted,
                    style = MaterialTheme.typography.labelMedium,
                )
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(
                        metricValue,
                        color = palette.textStrong,
                        fontSize = 38.sp,
                        lineHeight = 42.sp,
                        fontWeight = FontWeight.Black,
                    )
                    Text(
                        metricUnit,
                        modifier = Modifier.padding(
                            start = 5.dp,
                            bottom = 4.dp,
                        ),
                        color = palette.textMuted,
                        style = MaterialTheme.typography.bodySmall,
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
                    .size(176.dp)
                    .align(Alignment.CenterEnd)
                    .graphicsLayer {
                        translationX = 12.dp.toPx()
                        translationY = 7.dp.toPx()
                    },
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
        verticalAlignment = Alignment.Bottom,
    ) {
        Text(
            title,
            color = palette.textStrong,
            fontSize = 21.sp,
            lineHeight = 26.sp,
            fontWeight = FontWeight.Black,
            letterSpacing = (-0.4).sp,
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
        horizontalArrangement = Arrangement.spacedBy(7.dp),
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
        horizontalArrangement = Arrangement.spacedBy(7.dp),
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
    @DrawableRes imageRes: Int,
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
        contentPadding = PaddingValues(14.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(11.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ReferenceGlassImage(
                imageRes = imageRes,
                palette = palette,
                modifier = Modifier.size(86.dp),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(
                        title,
                        color = palette.textStrong,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Black,
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
                        style = MaterialTheme.typography.labelSmall,
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
                                .size(9.dp)
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
            horizontalArrangement = Arrangement.spacedBy(9.dp),
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
        contentPadding = PaddingValues(6.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            items.take(5).forEach { item ->
                val interactionSource = remember {
                    MutableInteractionSource()
                }
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .height(58.dp)
                        .clip(RoundedCornerShape(17.dp))
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
                                        Color.White.copy(alpha = 0.82f),
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
                        .padding(vertical = 6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Image(
                        painter = painterResource(item.iconRes),
                        contentDescription = item.label,
                        modifier = Modifier.size(25.dp),
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
    val shape = RoundedCornerShape(26.dp)
    val fillAlpha = if (strong) 0.76f else 0.58f
    val borderColor = if (danger) {
        palette.danger
    } else {
        Color.White.copy(alpha = 0.88f)
    }

    Column(
        modifier = modifier
            .shadow(
                elevation = if (danger) 5.dp else 9.dp,
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
                            Color.White.copy(alpha = fillAlpha - 0.12f),
                            palette.accentSoftSecondary.copy(alpha = 0.14f),
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
        verticalArrangement = Arrangement.spacedBy(10.dp),
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
    compact: Boolean = false,
) {
    val shape = RoundedCornerShape(if (compact) 15.dp else 18.dp)
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
                            Color.White.copy(
                                alpha = if (enabled) 0.74f else 0.40f
                            ),
                            if (enabled) {
                                palette.accentSoft.copy(alpha = 0.15f)
                            } else {
                                Color.Transparent
                            },
                        )
                    )
                }
            )
            .border(
                BorderStroke(
                    1.dp,
                    if (accent) {
                        Color.White.copy(alpha = 0.58f)
                    } else {
                        Color.White.copy(
                            alpha = if (enabled) 0.88f else 0.40f
                        )
                    },
                ),
                shape,
            )
            .heightIn(min = if (compact) 38.dp else 48.dp)
            .padding(
                horizontal = if (compact) 11.dp else 14.dp,
                vertical = if (compact) 8.dp else 11.dp,
            ),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text,
            color = when {
                !enabled -> palette.textMuted
                accent -> Color.White
                else -> palette.textStrong
            },
            style = if (compact) {
                MaterialTheme.typography.labelMedium
            } else {
                MaterialTheme.typography.labelLarge
            },
            fontWeight = FontWeight.ExtraBold,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun ReferenceSquareIconButton(
    symbol: String,
    palette: ReferenceDashboardPalette,
    onClick: () -> Unit,
) {
    val shape = RoundedCornerShape(17.dp)
    val interactionSource = remember { MutableInteractionSource() }
    Box(
        modifier = Modifier
            .size(46.dp)
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
                        Color.White.copy(alpha = 0.82f),
                        palette.accentSoft.copy(alpha = 0.18f),
                    )
                )
            )
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.90f),
                ),
                shape,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            symbol,
            color = palette.textStrong,
            fontSize = 22.sp,
            fontWeight = FontWeight.Bold,
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
        modifier = modifier.height(112.dp),
        palette = palette,
        contentPadding = PaddingValues(7.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(1.dp),
        ) {
            Image(
                painter = painterResource(item.iconRes),
                contentDescription = item.label,
                modifier = Modifier.size(38.dp),
            )
            Text(
                item.label,
                color = palette.textMuted,
                style = MaterialTheme.typography.labelSmall,
                textAlign = TextAlign.Center,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                item.value,
                color = if (item.healthy) {
                    palette.accent
                } else {
                    palette.danger
                },
                fontSize = 15.sp,
                lineHeight = 18.sp,
                fontWeight = FontWeight.Black,
                textAlign = TextAlign.Center,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
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
            .height(112.dp)
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
                        Color.White.copy(
                            alpha = if (item.enabled) 0.78f else 0.42f
                        ),
                        if (item.enabled) {
                            palette.accentSoft.copy(alpha = 0.15f)
                        } else {
                            Color.Transparent
                        },
                    )
                )
            )
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(
                        alpha = if (item.enabled) 0.90f else 0.42f
                    ),
                ),
                RoundedCornerShape(22.dp),
            )
            .padding(7.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Image(
            painter = painterResource(item.iconRes),
            contentDescription = item.label,
            modifier = Modifier.size(43.dp),
            alpha = if (item.enabled) 1f else 0.45f,
        )
        Text(
            item.label,
            modifier = Modifier.padding(top = 3.dp),
            color = if (item.enabled) {
                palette.textStrong
            } else {
                palette.textMuted
            },
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.ExtraBold,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        if (item.subtitle.isNotBlank()) {
            Text(
                item.subtitle,
                color = palette.textMuted,
                fontSize = 9.sp,
                lineHeight = 11.sp,
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
            .height(11.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(Color.White.copy(alpha = 0.68f))
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.88f),
                ),
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
            .background(Color.White.copy(alpha = 0.72f))
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.92f),
                ),
                RoundedCornerShape(999.dp),
            )
            .padding(
                horizontal = 10.dp,
                vertical = 6.dp,
            ),
        color = palette.accent,
        style = MaterialTheme.typography.labelSmall,
        fontWeight = FontWeight.ExtraBold,
    )
}

@Composable
private fun ReferenceGlassImage(
    @DrawableRes imageRes: Int,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(
                Brush.linearGradient(
                    listOf(
                        Color.White.copy(alpha = 0.80f),
                        palette.accentSoft.copy(alpha = 0.12f),
                    )
                )
            )
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.90f),
                ),
                RoundedCornerShape(20.dp),
            )
            .padding(5.dp),
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

@Composable
private fun ReferencePearlBackground(
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(
                Brush.linearGradient(
                    listOf(
                        palette.backgroundStart,
                        Color(0xFFF4FAFD),
                        palette.backgroundEnd,
                    )
                )
            ),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            palette.accentSoft.copy(alpha = 0.62f),
                            Color.Transparent,
                        ),
                        radius = 760f,
                    )
                )
        )
        content()
    }
}
