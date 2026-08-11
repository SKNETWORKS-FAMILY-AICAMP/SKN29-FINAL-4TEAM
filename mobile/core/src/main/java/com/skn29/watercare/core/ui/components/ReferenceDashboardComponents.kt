package com.skn29.watercare.core.ui.components

import androidx.annotation.DrawableRes
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.BoxWithConstraints
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
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontFamily
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
    accent = Color(0xFF0D7CFF),
    accentSecondary = Color(0xFF28C5F5),
    accentSoft = Color(0x331677FF),
    accentSoftSecondary = Color(0x2819C7D9),
    backgroundStart = Color(0xFFF8FCFF),
    backgroundEnd = Color(0xFFF4FBFF),
    textStrong = Color(0xFF0A2148),
    textMuted = Color(0xFF55738A),
    success = Color(0xFF22B998),
    warning = Color(0xFFE2A141),
    danger = Color(0xFFE95570),
)

val TechnicianReferencePalette = ReferenceDashboardPalette(
    accent = Color(0xFF00AFA9),
    accentSecondary = Color(0xFF268DDB),
    accentSoft = Color(0x330AB7B9),
    accentSoftSecondary = Color(0x282C95FF),
    backgroundStart = Color(0xFFF7FFFD),
    backgroundEnd = Color(0xFFF3FAFF),
    textStrong = Color(0xFF0B3040),
    textMuted = Color(0xFF56757B),
    success = Color(0xFF18B8A8),
    warning = Color(0xFFE5A146),
    danger = Color(0xFFEA5B70),
)

private val ReferenceWaterDropPanelShape = RoundedCornerShape(30.dp)

private val ReferenceWaterDropTileShape = RoundedCornerShape(26.dp)

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
    val enabled: Boolean = true,
    val onClick: () -> Unit = {},
)

@Composable
fun ReferenceDashboardScaffold(
    title: String,
    roleLabel: String,
    palette: ReferenceDashboardPalette,
    @DrawableRes backgroundRes: Int? = null,
    bottomItems: List<ReferenceBottomItem> = emptyList(),
    modifier: Modifier = Modifier,
    onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
    notificationEnabled: Boolean = false,
    supportEnabled: Boolean = false,
    content: @Composable ColumnScope.() -> Unit,
) {
    ReferencePearlBackground(
        palette = palette,
        backgroundRes = backgroundRes,
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
                                start = 12.dp,
                                end = 12.dp,
                                bottom = 7.dp,
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
                        top = 12.dp,
                        bottom = 112.dp,
                    ),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                ReferenceDashboardHeader(
                    roleLabel = roleLabel,
                    palette = palette,
                    title = title,
                    onNotification = onNotification,
                    onSupport = onSupport,
                    notificationEnabled = notificationEnabled,
                    supportEnabled = supportEnabled,
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
        modifier = modifier.fillMaxWidth(),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(
            horizontal = 18.dp,
            vertical = 18.dp,
        ),
    ) {
        BoxWithConstraints(
            modifier = Modifier.fillMaxWidth(),
        ) {
            val compact = maxWidth < 360.dp
            val imageSize = if (compact) 118.dp else 150.dp
            val titleSize = if (compact) 22.sp else 25.sp

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = if (compact) 178.dp else 196.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        title,
                        color = palette.textStrong,
                        fontFamily = FontFamily.SansSerif,
                        fontSize = titleSize,
                        lineHeight = if (compact) 28.sp else 32.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = (-0.2).sp,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        subtitle,
                        color = palette.textMuted,
                        style = MaterialTheme.typography.bodyMedium,
                        lineHeight = 22.sp,
                        maxLines = 4,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Image(
                    painter = painterResource(imageRes),
                    contentDescription = null,
                    modifier = Modifier.size(imageSize),
                    contentScale = ContentScale.Fit,
                )
            }
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
                    fontWeight = FontWeight.SemiBold,
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
                    accent = true,
                    compact = true,
                )
            }
        }
    }
}

@Composable
fun ReferenceBackendStatusCard(
    title: String,
    message: String,
    palette: ReferenceDashboardPalette,
    warning: Boolean = false,
    actionLabel: String? = null,
    onAction: () -> Unit = {},
) {
    ReferenceGlassPanel(
        modifier = Modifier.fillMaxWidth(),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(18.dp),
    ) {
        Text(
            title,
            color = if (warning) palette.warning else palette.textStrong,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            message,
            color = palette.textMuted,
            style = MaterialTheme.typography.bodyMedium,
            lineHeight = 22.sp,
            maxLines = 3,
            overflow = TextOverflow.Ellipsis,
        )
        if (!actionLabel.isNullOrBlank()) {
            ReferenceGlassButton(
                text = actionLabel,
                palette = palette,
                onClick = onAction,
                accent = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun ReferenceBrandMark(
    palette: ReferenceDashboardPalette,
) {
    Canvas(modifier = Modifier.size(44.dp)) {
        val droplet = Path().apply {
            moveTo(size.width * 0.50f, size.height * 0.05f)
            cubicTo(
                size.width * 0.30f,
                size.height * 0.30f,
                size.width * 0.12f,
                size.height * 0.50f,
                size.width * 0.12f,
                size.height * 0.68f,
            )
            cubicTo(
                size.width * 0.12f,
                size.height * 0.88f,
                size.width * 0.29f,
                size.height * 0.98f,
                size.width * 0.50f,
                size.height * 0.98f,
            )
            cubicTo(
                size.width * 0.71f,
                size.height * 0.98f,
                size.width * 0.88f,
                size.height * 0.88f,
                size.width * 0.88f,
                size.height * 0.68f,
            )
            cubicTo(
                size.width * 0.88f,
                size.height * 0.50f,
                size.width * 0.70f,
                size.height * 0.30f,
                size.width * 0.50f,
                size.height * 0.05f,
            )
            close()
        }

        drawPath(
            path = droplet,
            brush = Brush.linearGradient(
                listOf(
                    palette.accent,
                    palette.accentSecondary,
                )
            ),
        )
        drawCircle(
            color = Color.White.copy(alpha = 0.82f),
            radius = size.minDimension * 0.17f,
            center = Offset(
                size.width * 0.43f,
                size.height * 0.59f,
            ),
        )
    }
}

@Composable
fun ReferenceDashboardHeader(
    roleLabel: String,
    palette: ReferenceDashboardPalette,
    title: String = "정수기 딜러",
    onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
    notificationEnabled: Boolean = false,
    supportEnabled: Boolean = false,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 2.dp, vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            ReferenceBrandMark(palette)
            Text(
                title,
                color = palette.textStrong,
                fontFamily = FontFamily.SansSerif,
                fontSize = 26.sp,
                lineHeight = 32.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = (-0.4).sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ReferenceSquareIconButton(
                icon = ReferenceHeaderIcon.Notification,
                palette = palette,
                onClick = onNotification,
                enabled = notificationEnabled,
            )
            ReferenceSquareIconButton(
                icon = ReferenceHeaderIcon.Support,
                palette = palette,
                onClick = onSupport,
                enabled = supportEnabled,
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
    roleLabel: String? = null,
    imageEmphasis: Float = 1f,
) {
    ReferenceGlassPanel(
        modifier = modifier.fillMaxWidth(),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(
            horizontal = 18.dp,
            vertical = 18.dp,
        ),
    ) {
        BoxWithConstraints(
            modifier = Modifier.fillMaxWidth(),
        ) {
            val compact = maxWidth < 360.dp
            val imageSize = (
                if (compact) 148.dp else 180.dp
            ) * imageEmphasis.coerceIn(0.94f, 1.12f)
            val heroHeight = if (compact) 214.dp else 242.dp
            val firstLine = greeting.substringBefore("\n")
            val secondLine = greeting.substringAfter("\n", "")

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = heroHeight),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    if (!roleLabel.isNullOrBlank()) {
                        ReferenceRoleChip(
                            roleLabel = roleLabel,
                            palette = palette,
                        )
                    }

                    Text(
                        firstLine,
                        color = palette.textStrong,
                        fontFamily = FontFamily.SansSerif,
                        fontSize = if (compact) 21.sp else 24.sp,
                        lineHeight = if (compact) 27.sp else 30.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = (-0.35).sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )

                    if (secondLine.isNotBlank()) {
                        Text(
                            secondLine,
                            color = palette.accent,
                            fontFamily = FontFamily.SansSerif,
                            fontSize = if (compact) 28.sp else 32.sp,
                            lineHeight = if (compact) 33.sp else 38.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = (-0.55).sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }

                    Text(
                        subtitle,
                        color = palette.textMuted,
                        fontSize = if (compact) 13.5.sp else 15.sp,
                        lineHeight = if (compact) 20.5.sp else 23.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis,
                    )
                }

                Box(
                    modifier = Modifier.size(imageSize),
                    contentAlignment = Alignment.Center,
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .clip(CircleShape)
                            .background(
                                Brush.radialGradient(
                                    listOf(
                                        Color.White.copy(alpha = 0.46f),
                                        palette.accentSoft.copy(alpha = 0.20f),
                                        Color.Transparent,
                                    )
                                )
                            ),
                    )

                    Image(
                        painter = painterResource(imageRes),
                        contentDescription = null,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(1.dp),
                        contentScale = ContentScale.Fit,
                    )
                }
            }
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
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            title,
            color = palette.textStrong,
            fontFamily = FontFamily.SansSerif,
            fontSize = 20.sp,
            lineHeight = 24.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = (-0.35).sp,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )

        if (!trailing.isNullOrBlank()) {
            Text(
                trailing,
                color = palette.accent.copy(alpha = 0.90f),
                fontSize = 11.5.sp,
                lineHeight = 15.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
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
    primaryActionEnabled: Boolean = true,
    secondaryActionEnabled: Boolean = true,
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
                Text(
                    title,
                    color = palette.textStrong,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                ReferencePill(
                    text = badge,
                    palette = palette,
                )
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
                enabled = primaryActionEnabled,
                modifier = Modifier.weight(1f),
            )
            ReferenceGlassButton(
                text = secondaryActionLabel,
                palette = palette,
                onClick = onSecondaryAction,
                enabled = secondaryActionEnabled,
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
        contentPadding = PaddingValues(5.dp),
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
                        .height(60.dp)
                        .clip(RoundedCornerShape(20.dp))
                        .graphicsLayer {
                            alpha = if (item.enabled) 1f else 0.62f
                        }
                        .clickable(
                            enabled = item.enabled,
                            role = Role.Button,
                            interactionSource = interactionSource,
                            indication = LocalIndication.current,
                            onClick = item.onClick,
                        )
                        .background(
                            if (item.selected) {
                                Brush.verticalGradient(
                                    listOf(
                                        Color.White.copy(alpha = 0.96f),
                                        palette.accentSoft.copy(alpha = 0.20f),
                                        Color.White.copy(alpha = 0.88f),
                                    )
                                )
                            } else {
                                Brush.verticalGradient(
                                    listOf(
                                        Color.Transparent,
                                        Color.Transparent,
                                    )
                                )
                            }
                        )
                        .padding(vertical = 5.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Image(
                        painter = painterResource(item.iconRes),
                        contentDescription = item.label,
                        modifier = Modifier.size(24.dp),
                    )

                    Text(
                        item.label,
                        modifier = Modifier.padding(top = 2.dp),
                        color = if (item.selected) {
                            palette.accent
                        } else {
                            palette.textMuted
                        },
                        fontSize = 11.sp,
                        lineHeight = 12.sp,
                        fontWeight = if (item.selected) {
                            FontWeight.Bold
                        } else {
                            FontWeight.Medium
                        },
                        maxLines = 1,
                    )

                    if (item.selected) {
                        Box(
                            modifier = Modifier
                                .padding(top = 2.dp)
                                .size(
                                    width = 22.dp,
                                    height = 2.5.dp,
                                )
                                .clip(RoundedCornerShape(999.dp))
                                .background(palette.accent)
                        )
                    }
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
    val shape = if (danger) {
        RoundedCornerShape(24.dp)
    } else {
        ReferenceWaterDropPanelShape
    }

    val surfaceAlpha = if (strong) 0.945f else 0.885f
    val accentAlpha = if (strong) 0.032f else 0.018f
    val shadowAlpha = if (strong) 0.085f else 0.055f

    val borderBrush = if (danger) {
        Brush.linearGradient(
            listOf(
                palette.danger,
                palette.danger,
            )
        )
    } else {
        Brush.linearGradient(
            listOf(
                Color.White.copy(alpha = 0.98f),
                palette.accent.copy(alpha = 0.28f),
                palette.accentSecondary.copy(alpha = 0.18f),
                Color.White.copy(alpha = 0.94f),
            )
        )
    }

    Column(
        modifier = modifier
            .shadow(
                elevation = if (danger) {
                    4.dp
                } else if (strong) {
                    8.dp
                } else {
                    5.dp
                },
                shape = shape,
                ambientColor = if (danger) {
                    palette.danger.copy(alpha = 0.12f)
                } else {
                    palette.accent.copy(alpha = shadowAlpha)
                },
                spotColor = if (danger) {
                    palette.danger.copy(alpha = 0.14f)
                } else {
                    palette.accentSecondary.copy(
                        alpha = shadowAlpha * 0.80f
                    )
                },
                clip = false,
            )
            .clip(shape)
            .background(
                if (danger) {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.98f),
                            Color.White.copy(alpha = 0.94f),
                        )
                    )
                } else {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = surfaceAlpha),
                            palette.accentSoft.copy(alpha = accentAlpha),
                            Color.White.copy(
                                alpha = surfaceAlpha * 0.96f
                            ),
                        )
                    )
                }
            )
            .drawBehind {
                if (!danger) {
                    drawLine(
                        color = Color.White.copy(
                            alpha = if (strong) 0.88f else 0.72f
                        ),
                        start = Offset(
                            x = size.width * 0.10f,
                            y = 1.5.dp.toPx(),
                        ),
                        end = Offset(
                            x = size.width * 0.76f,
                            y = 1.5.dp.toPx(),
                        ),
                        strokeWidth = 1.1.dp.toPx(),
                        cap = StrokeCap.Round,
                    )

                    drawOval(
                        color = palette.accent.copy(
                            alpha = if (strong) 0.028f else 0.016f
                        ),
                        topLeft = Offset(
                            x = size.width * 0.72f,
                            y = size.height * 0.68f,
                        ),
                        size = Size(
                            width = size.width * 0.34f,
                            height = size.height * 0.30f,
                        ),
                    )
                }
            }
            .border(
                BorderStroke(
                    width = if (danger) 1.5.dp else 1.05.dp,
                    brush = borderBrush,
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
    val shape = RoundedCornerShape(999.dp)
    val interactionSource = remember { MutableInteractionSource() }

    val accentPrimaryAlpha = if (enabled) 0.98f else 0.30f
    val accentSecondaryAlpha = if (enabled) 0.88f else 0.22f
    val neutralAlpha = if (enabled) 0.220f else 0.060f
    val buttonGlowAlpha = if (accent) 0.46f else 0.26f

    Row(
        modifier = modifier
            .shadow(
                elevation = if (accent) 15.dp else 8.dp,
                shape = shape,
                ambientColor = palette.accent.copy(
                    alpha = buttonGlowAlpha
                ),
                spotColor = palette.accentSecondary.copy(
                    alpha = buttonGlowAlpha * 0.92f
                ),
                clip = false,
            )
            .clip(shape)
            .clickable(
                enabled = enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = LocalIndication.current,
                onClick = onClick,
            )
            .background(
                if (accent) {
                    Brush.linearGradient(
                        listOf(
                            palette.accent.copy(
                                alpha = accentPrimaryAlpha
                            ),
                            palette.accentSecondary.copy(
                                alpha = accentSecondaryAlpha
                            ),
                            palette.accent.copy(
                                alpha = accentPrimaryAlpha * 0.76f
                            ),
                        )
                    )
                } else {
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = neutralAlpha),
                            palette.accentSoft.copy(alpha = 0.180f),
                            palette.accentSecondary.copy(alpha = 0.120f),
                            Color.Transparent,
                            Color.White.copy(alpha = neutralAlpha * 0.52f),
                        )
                    )
                }
            )
            .drawBehind {
                drawOval(
                    color = Color.White.copy(
                        alpha = if (accent) 0.38f else 0.28f
                    ),
                    topLeft = Offset(
                        x = size.width * 0.08f,
                        y = size.height * 0.05f,
                    ),
                    size = Size(
                        width = size.width * 0.38f,
                        height = size.height * 0.34f,
                    ),
                )

                drawLine(
                    color = Color.White.copy(
                        alpha = if (accent) 0.86f else 0.62f
                    ),
                    start = Offset(
                        x = size.width * 0.12f,
                        y = 1.5.dp.toPx(),
                    ),
                    end = Offset(
                        x = size.width * 0.72f,
                        y = 1.5.dp.toPx(),
                    ),
                    strokeWidth = 1.2.dp.toPx(),
                    cap = StrokeCap.Round,
                )
            }
            .border(
                BorderStroke(
                    width = if (accent) 1.70.dp else 1.50.dp,
                    brush = Brush.linearGradient(
                        listOf(
                            Color.White.copy(
                                alpha = if (enabled) 0.98f else 0.40f
                            ),
                            palette.accent.copy(
                                alpha = if (accent) 0.98f else 0.84f
                            ),
                            palette.accentSecondary.copy(
                                alpha = if (accent) 0.92f else 0.72f
                            ),
                            Color.White.copy(
                                alpha = if (enabled) 0.86f else 0.32f
                            ),
                        )
                    ),
                ),
                shape,
            )
            .heightIn(min = if (compact) 44.dp else 56.dp)
            .padding(
                horizontal = if (compact) 13.dp else 17.dp,
                vertical = if (compact) 8.dp else 12.dp,
            ),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = if (enabled) "$text  ›" else text,
            color = when {
                !enabled -> palette.textMuted
                accent -> Color.White
                else -> palette.accent
            },
            style = if (compact) {
                MaterialTheme.typography.labelMedium
            } else {
                MaterialTheme.typography.labelLarge
            },
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

private enum class ReferenceHeaderIcon {
    Notification,
    Support,
}

@Composable
private fun ReferenceRoleChip(
    roleLabel: String,
    palette: ReferenceDashboardPalette,
) {
    Row(
        modifier = Modifier
            .shadow(
                elevation = 6.dp,
                shape = RoundedCornerShape(999.dp),
                ambientColor = palette.accent.copy(alpha = 0.24f),
                spotColor = palette.accentSecondary.copy(alpha = 0.20f),
                clip = false,
            )
            .clip(RoundedCornerShape(999.dp))
            .background(
                Brush.linearGradient(
                    listOf(
                        Color.White.copy(alpha = 0.20f),
                        palette.accentSoft.copy(alpha = 0.28f),
                        palette.accentSecondary.copy(alpha = 0.10f),
                        Color.Transparent,
                    )
                )
            )
            .border(
                BorderStroke(
                    1.3.dp,
                    palette.accent.copy(alpha = 0.78f),
                ),
                RoundedCornerShape(999.dp),
            )
            .padding(
                horizontal = 12.dp,
                vertical = 8.dp,
            ),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Canvas(modifier = Modifier.size(16.dp)) {
            val strokeWidth = 1.7.dp.toPx()
            drawCircle(
                color = palette.accent,
                radius = size.minDimension * 0.17f,
                center = Offset(
                    x = size.width * 0.50f,
                    y = size.height * 0.30f,
                ),
                style = Stroke(width = strokeWidth),
            )
            drawArc(
                color = palette.accent,
                startAngle = 205f,
                sweepAngle = 130f,
                useCenter = false,
                topLeft = Offset(
                    x = size.width * 0.20f,
                    y = size.height * 0.48f,
                ),
                size = Size(
                    width = size.width * 0.60f,
                    height = size.height * 0.45f,
                ),
                style = Stroke(
                    width = strokeWidth,
                    cap = StrokeCap.Round,
                ),
            )
        }
        Text(
            roleLabel,
            color = palette.accent,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
        )
        Canvas(modifier = Modifier.size(10.dp)) {
            val strokeWidth = 1.5.dp.toPx()
            drawLine(
                color = palette.accent,
                start = Offset(
                    x = size.width * 0.20f,
                    y = size.height * 0.36f,
                ),
                end = Offset(
                    x = size.width * 0.50f,
                    y = size.height * 0.66f,
                ),
                strokeWidth = strokeWidth,
                cap = StrokeCap.Round,
            )
            drawLine(
                color = palette.accent,
                start = Offset(
                    x = size.width * 0.50f,
                    y = size.height * 0.66f,
                ),
                end = Offset(
                    x = size.width * 0.80f,
                    y = size.height * 0.36f,
                ),
                strokeWidth = strokeWidth,
                cap = StrokeCap.Round,
            )
        }
    }
}

@Composable
private fun ReferenceSquareIconButton(
    icon: ReferenceHeaderIcon,
    palette: ReferenceDashboardPalette,
    onClick: () -> Unit,
enabled: Boolean = true,
) {
    val shape = CircleShape
    val interactionSource = remember { MutableInteractionSource() }

    Box(
        modifier = Modifier
            .size(44.dp)
            .shadow(
                elevation = 6.dp,
                shape = shape,
                ambientColor = palette.accent.copy(alpha = 0.18f),
                spotColor = palette.accentSecondary.copy(alpha = 0.16f),
                clip = false,
            )
            .clip(shape)
            .graphicsLayer {
                alpha = if (enabled) 1f else 0.58f
            }
            .clickable(
                enabled = enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = LocalIndication.current,
                onClick = onClick,
            )
            .background(
                Brush.radialGradient(
                    listOf(
                        Color.White.copy(alpha = 0.72f),
                        palette.accentSoft.copy(alpha = 0.20f),
                        palette.accentSecondary.copy(alpha = 0.10f),
                        Color.Transparent,
                    )
                )
            )
            .drawBehind {
                drawOval(
                    color = Color.White.copy(alpha = 0.52f),
                    topLeft = Offset(
                        x = size.width * 0.20f,
                        y = size.height * 0.10f,
                    ),
                    size = Size(
                        width = size.width * 0.40f,
                        height = size.height * 0.22f,
                    ),
                )
            }
            .border(
                BorderStroke(
                    1.6.dp,
                    brush = Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = 0.99f),
                            palette.accent.copy(alpha = 0.82f),
                            Color.White.copy(alpha = 0.90f),
                        )
                    ),
                ),
                shape,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.size(21.dp)) {
            val strokeWidth = 1.8.dp.toPx()
            val stroke = Stroke(
                width = strokeWidth,
                cap = StrokeCap.Round,
                join = StrokeJoin.Round,
            )

            when (icon) {
                ReferenceHeaderIcon.Notification -> {
                    val bell = Path().apply {
                        moveTo(
                            x = size.width * 0.28f,
                            y = size.height * 0.68f,
                        )
                        cubicTo(
                            x1 = size.width * 0.34f,
                            y1 = size.height * 0.58f,
                            x2 = size.width * 0.34f,
                            y2 = size.height * 0.48f,
                            x3 = size.width * 0.34f,
                            y3 = size.height * 0.39f,
                        )
                        cubicTo(
                            x1 = size.width * 0.34f,
                            y1 = size.height * 0.18f,
                            x2 = size.width * 0.66f,
                            y2 = size.height * 0.18f,
                            x3 = size.width * 0.66f,
                            y3 = size.height * 0.39f,
                        )
                        cubicTo(
                            x1 = size.width * 0.66f,
                            y1 = size.height * 0.48f,
                            x2 = size.width * 0.66f,
                            y2 = size.height * 0.58f,
                            x3 = size.width * 0.72f,
                            y3 = size.height * 0.68f,
                        )
                    }
                    drawPath(
                        path = bell,
                        color = palette.textStrong,
                        style = stroke,
                    )
                    drawLine(
                        color = palette.textStrong,
                        start = Offset(
                            x = size.width * 0.24f,
                            y = size.height * 0.70f,
                        ),
                        end = Offset(
                            x = size.width * 0.76f,
                            y = size.height * 0.70f,
                        ),
                        strokeWidth = strokeWidth,
                        cap = StrokeCap.Round,
                    )
                    drawArc(
                        color = palette.textStrong,
                        startAngle = 15f,
                        sweepAngle = 150f,
                        useCenter = false,
                        topLeft = Offset(
                            x = size.width * 0.42f,
                            y = size.height * 0.69f,
                        ),
                        size = Size(
                            width = size.width * 0.16f,
                            height = size.height * 0.14f,
                        ),
                        style = stroke,
                    )
                }

                ReferenceHeaderIcon.Support -> {
                    drawArc(
                        color = palette.textStrong,
                        startAngle = 180f,
                        sweepAngle = 180f,
                        useCenter = false,
                        topLeft = Offset(
                            x = size.width * 0.18f,
                            y = size.height * 0.18f,
                        ),
                        size = Size(
                            width = size.width * 0.64f,
                            height = size.height * 0.64f,
                        ),
                        style = stroke,
                    )
                    drawLine(
                        color = palette.textStrong,
                        start = Offset(
                            x = size.width * 0.20f,
                            y = size.height * 0.50f,
                        ),
                        end = Offset(
                            x = size.width * 0.20f,
                            y = size.height * 0.72f,
                        ),
                        strokeWidth = strokeWidth * 1.8f,
                        cap = StrokeCap.Round,
                    )
                    drawLine(
                        color = palette.textStrong,
                        start = Offset(
                            x = size.width * 0.80f,
                            y = size.height * 0.50f,
                        ),
                        end = Offset(
                            x = size.width * 0.80f,
                            y = size.height * 0.72f,
                        ),
                        strokeWidth = strokeWidth * 1.8f,
                        cap = StrokeCap.Round,
                    )
                    drawArc(
                        color = palette.textStrong,
                        startAngle = 0f,
                        sweepAngle = 95f,
                        useCenter = false,
                        topLeft = Offset(
                            x = size.width * 0.50f,
                            y = size.height * 0.55f,
                        ),
                        size = Size(
                            width = size.width * 0.31f,
                            height = size.height * 0.28f,
                        ),
                        style = stroke,
                    )
                    drawCircle(
                        color = palette.textStrong,
                        radius = strokeWidth,
                        center = Offset(
                            x = size.width * 0.51f,
                            y = size.height * 0.82f,
                        ),
                    )
                }
            }
        }
    }
}

@Composable
private fun ReferenceStatusTile(
    item: ReferenceStatusItem,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    ReferenceGlassPanel(
        modifier = modifier.height(108.dp),
        palette = palette,
        danger = !item.healthy &&
            item.label.contains("긴급"),
        contentPadding = PaddingValues(
            horizontal = 6.dp,
            vertical = 8.dp,
        ),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .background(
                        Brush.radialGradient(
                            listOf(
                                Color.White.copy(alpha = 0.94f),
                                palette.accentSoft.copy(alpha = 0.16f),
                            )
                        )
                    )
                    .border(
                        BorderStroke(
                            1.dp,
                            Color.White.copy(alpha = 0.96f),
                        ),
                        CircleShape,
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(item.iconRes),
                    contentDescription = item.label,
                    modifier = Modifier.size(28.dp),
                )
            }

            Text(
                item.label,
                color = palette.textMuted,
                fontFamily = FontFamily.SansSerif,
                fontSize = 10.5.sp,
                lineHeight = 13.sp,
                fontWeight = FontWeight.Medium,
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
                fontFamily = FontFamily.SansSerif,
                fontSize = 14.sp,
                lineHeight = 16.sp,
                fontWeight = FontWeight.ExtraBold,
                textAlign = TextAlign.Center,
                maxLines = 2,
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
    val shape = ReferenceWaterDropTileShape
    val tagModifier = if (item.testTag.isNullOrBlank()) {
        Modifier
    } else {
        Modifier.testTag(item.testTag)
    }

    Column(
        modifier = modifier
            .then(tagModifier)
            .height(118.dp)
            .shadow(
                elevation = if (item.enabled) 5.dp else 1.dp,
                shape = shape,
                ambientColor = palette.accent.copy(
                    alpha = if (item.enabled) 0.10f else 0.03f
                ),
                spotColor = palette.accentSecondary.copy(
                    alpha = if (item.enabled) 0.08f else 0.02f
                ),
                clip = false,
            )
            .clip(shape)
            .clickable(
                enabled = item.enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = LocalIndication.current,
                onClick = item.onClick,
            )
            .background(
                Brush.verticalGradient(
                    listOf(
                        Color.White.copy(
                            alpha = if (item.enabled) 0.95f else 0.78f
                        ),
                        palette.accentSoft.copy(
                            alpha = if (item.enabled) 0.075f else 0.035f
                        ),
                        Color.White.copy(
                            alpha = if (item.enabled) 0.82f else 0.58f
                        ),
                    )
                )
            )
            .border(
                BorderStroke(
                    width = 1.15.dp,
                    brush = Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = 0.98f),
                            palette.accent.copy(
                                alpha = if (item.enabled) 0.28f else 0.10f
                            ),
                            Color.White.copy(alpha = 0.92f),
                        )
                    ),
                ),
                shape,
            )
            .padding(
                horizontal = 5.dp,
                vertical = 7.dp,
            ),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .size(48.dp)
                .clip(CircleShape)
                .background(
                    Brush.radialGradient(
                        listOf(
                            Color.White.copy(alpha = 0.98f),
                            palette.accentSoft.copy(
                                alpha = if (item.enabled) 0.18f else 0.06f
                            ),
                        )
                    )
                )
                .border(
                    BorderStroke(
                        1.dp,
                        Color.White.copy(alpha = 0.96f),
                    ),
                    CircleShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(item.iconRes),
                contentDescription = item.label,
                modifier = Modifier.size(32.dp),
                alpha = if (item.enabled) 1f else 0.68f,
            )
        }

        Text(
            text = item.label,
            modifier = Modifier.padding(top = 5.dp),
            color = if (item.enabled) {
                palette.textStrong
            } else {
                palette.textMuted
            },
            fontFamily = FontFamily.SansSerif,
            fontSize = 11.5.sp,
            lineHeight = 15.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )

        if (item.subtitle.isNotBlank()) {
            Text(
                text = if (item.enabled) {
                    item.subtitle
                } else {
                    "준비 중"
                },
                color = palette.textMuted.copy(alpha = 0.78f),
                fontSize = 9.5.sp,
                lineHeight = 12.sp,
                fontWeight = FontWeight.Medium,
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
            .background(Color.White.copy(alpha = 0.30f))
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(alpha = 0.68f),
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
            .background(
                Brush.linearGradient(
                    listOf(
                        Color.White.copy(alpha = 0.22f),
                        palette.accentSoft.copy(alpha = 0.14f),
                        Color.Transparent,
                    )
                )
            )
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
        fontWeight = FontWeight.Medium,
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
                        Color.White.copy(alpha = 0.13f),
                        palette.accentSoft.copy(alpha = 0.025f),
                        palette.accentSecondary.copy(alpha = 0.04f),
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
    @DrawableRes backgroundRes: Int? = null,
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
        backgroundRes?.let { resource ->
            Image(
                painter = painterResource(resource),
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
                alpha = 0.40f,
            )
        }

        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.010f),
                            Color.Transparent,
                            Color.White.copy(alpha = 0.018f),
                        )
                    )
                )
        )

        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            palette.accentSoft.copy(alpha = 0.025f),
                            Color.Transparent,
                        ),
                        radius = 760f,
                    )
                )
        )

        content()
    }
}
