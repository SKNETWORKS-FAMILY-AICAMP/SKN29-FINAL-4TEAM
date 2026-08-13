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
    val darkSurface: Boolean = false,
    val sunsetBackground: Boolean = false,
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
    accent = Color(0xFF43E2DE),
    accentSecondary = Color(0xFF49A8FF),
    accentSoft = Color(0x3343E2DE),
    accentSoftSecondary = Color(0x2849A8FF),
    backgroundStart = Color(0xFF063B55),
    backgroundEnd = Color(0xFF052A40),
    textStrong = Color(0xFFF2FCFF),
    textMuted = Color(0xFFB9D8E3),
    success = Color(0xFF55E0C9),
    warning = Color(0xFFFFC66A),
    danger = Color(0xFFFF7A8E),
    darkSurface = true,
)

private val ReferenceWaterDropPanelShape = RoundedCornerShape(32.dp)

private val ReferenceWaterDropTileShape = RoundedCornerShape(28.dp)

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
    backgroundImageAlpha: Float = 0.54f,
        @DrawableRes brandLogoRes: Int? = null,
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
        imageAlpha = backgroundImageAlpha,
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
                        start = 18.dp,
                        end = 18.dp,
                        top = 14.dp,
                        bottom = 116.dp,
                    ),
                verticalArrangement = Arrangement.spacedBy(18.dp),
            ) {
                ReferenceDashboardHeader(
                    roleLabel = roleLabel,
                    palette = palette,
                    title = title,
                    brandLogoRes = brandLogoRes,
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
                    .size(24.dp)
                    .clip(CircleShape)
                    .background(
                        if (warning) {
                            palette.warning.copy(alpha = 0.14f)
                        } else {
                            palette.success.copy(alpha = 0.14f)
                        }
                    )
                    .border(
                        BorderStroke(
                            1.dp,
                            if (warning) {
                                palette.warning.copy(alpha = 0.30f)
                            } else {
                                palette.success.copy(alpha = 0.30f)
                            },
                        ),
                        CircleShape,
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(9.dp)
                        .clip(CircleShape)
                        .background(
                            if (warning) {
                                palette.warning
                            } else {
                                palette.success
                            }
                        )
                )
            }
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
                if (palette.darkSurface) {
                    listOf(
                        palette.accent,
                        palette.accentSecondary,
                    )
                } else {
                    listOf(
                        Color.White,
                        Color(0xFFBDEBFF),
                    )
                }
            ),
        )
        drawCircle(
            color = if (palette.darkSurface) {
                Color.White.copy(alpha = 0.86f)
            } else {
                palette.accent.copy(alpha = 0.94f)
            },
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
    title: String = "WaterBridge",
        @DrawableRes brandLogoRes: Int? = null,
onNotification: () -> Unit = {},
    onSupport: () -> Unit = {},
    notificationEnabled: Boolean = false,
    supportEnabled: Boolean = false,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                start = 2.dp,
                end = 2.dp,
                top = 4.dp,
                bottom = 6.dp,
            ),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (brandLogoRes != null) {
                Image(
                    painter = painterResource(brandLogoRes),
                    contentDescription = "WaterBridge logo",
                    modifier = Modifier.size(58.dp),
                    contentScale = ContentScale.Fit,
                )
            } else {
                ReferenceBrandMark(palette)
            }
            Column(
                verticalArrangement = Arrangement.spacedBy(1.dp),
            ) {
                Text(
                    title,
                    color = if (palette.darkSurface) {
                        palette.textStrong
                    } else {
                        Color.White
                    },
                    fontFamily = FontFamily.SansSerif,
                    fontSize = 25.sp,
                    lineHeight = 29.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.55).sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    if (roleLabel.contains("기사")) {
                        "WaterBridge Field Service"
                    } else {
                        "WaterBridge Home Service"
                    },
                    color = if (palette.darkSurface) {
                        palette.textMuted.copy(alpha = 0.82f)
                    } else {
                        Color.White.copy(alpha = 0.84f)
                    },
                    fontSize = 10.5.sp,
                    lineHeight = 13.sp,
                    fontWeight = FontWeight.Medium,
                    letterSpacing = 0.3.sp,
                    maxLines = 1,
                )
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
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
    summaryItems: List<ReferenceStatusItem> = emptyList(),
) {
    ReferenceGlassPanel(
        modifier = modifier.fillMaxWidth(),
        palette = palette,
        strong = true,
        contentPadding = PaddingValues(
            horizontal = 20.dp,
            vertical = 20.dp,
        ),
    ) {
        BoxWithConstraints(
            modifier = Modifier.fillMaxWidth(),
        ) {
            val compact = maxWidth < 430.dp
            val imageSize = (
                if (compact) 118.dp else 174.dp
            ) * imageEmphasis.coerceIn(0.94f, 1.06f)
            val heroHeight = if (compact) 250.dp else 264.dp
            val firstLine = greeting.substringBefore("\n")
            val secondLine = greeting.substringAfter("\n", "")

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = heroHeight),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        text = if (palette.darkSurface) {
                            "FIELD SERVICE"
                        } else {
                            "SMART WATER CARE"
                        },
                        color = palette.accent.copy(alpha = 0.88f),
                        fontSize = 10.sp,
                        lineHeight = 12.sp,
                        fontWeight = FontWeight.ExtraBold,
                        letterSpacing = 1.15.sp,
                        maxLines = 1,
                    )

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
                        fontSize = if (compact) 23.sp else 28.sp,
                        lineHeight = if (compact) 29.sp else 34.sp,
                        fontWeight = FontWeight.ExtraBold,
                        letterSpacing = (-0.45).sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )

                    if (secondLine.isNotBlank()) {
                        Text(
                            secondLine,
                            color = palette.accent,
                            fontFamily = FontFamily.SansSerif,
                            fontSize = if (compact) 28.sp else 36.sp,
                            lineHeight = if (compact) 34.sp else 42.sp,
                            fontWeight = FontWeight.Black,
                            letterSpacing = (-0.75).sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }

                    Text(
                        subtitle,
                        color = palette.textMuted,
                        fontSize = if (compact) 13.sp else 15.sp,
                        lineHeight = if (compact) 20.sp else 23.sp,
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
                            .border(
                                BorderStroke(
                                    1.dp,
                                    Color.White.copy(
                                        alpha = if (
                                            palette.darkSurface
                                        ) 0.20f else 0.78f
                                    ),
                                ),
                                CircleShape,
                            )
                            .background(
                                Brush.radialGradient(
                                    listOf(
                                        Color.White.copy(
                                            alpha = if (
                                                palette.darkSurface
                                            ) {
                                                0.16f
                                            } else {
                                                0.62f
                                            }
                                        ),
                                        palette.accentSoft.copy(
                                            alpha = if (
                                                palette.darkSurface
                                            ) {
                                                0.38f
                                            } else {
                                                0.24f
                                            }
                                        ),
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
                            .padding(2.dp),
                        contentScale = ContentScale.Fit,
                    )
                }
            }
        }

        if (summaryItems.isNotEmpty()) {
            ReferenceHeroSummaryStrip(
                items = summaryItems,
                palette = palette,
            )
        }
    }
}

@Composable
private fun ReferenceHeroSummaryStrip(
    items: List<ReferenceStatusItem>,
    palette: ReferenceDashboardPalette,
) {
    val shape = RoundedCornerShape(22.dp)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(
                if (palette.darkSurface) {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.105f),
                            Color(0xFF073B55).copy(alpha = 0.46f),
                        )
                    )
                } else {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.78f),
                            Color.White.copy(alpha = 0.52f),
                        )
                    )
                }
            )
            .border(
                BorderStroke(
                    1.dp,
                    Color.White.copy(
                        alpha = if (
                            palette.darkSurface
                        ) 0.24f else 0.82f
                    ),
                ),
                shape,
            )
            .padding(
                horizontal = 8.dp,
                vertical = 12.dp,
            ),
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        items.take(4).forEach { item ->
            Column(
                modifier = Modifier.weight(1f),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Image(
                    painter = painterResource(item.iconRes),
                    contentDescription = null,
                    modifier = Modifier.size(24.dp),
                )
                Text(
                    item.label,
                    color = palette.textMuted,
                    fontSize = 11.sp,
                    lineHeight = 14.sp,
                    fontWeight = FontWeight.Medium,
                    textAlign = TextAlign.Center,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    item.value,
                    color = if (item.healthy) {
                        palette.textStrong
                    } else {
                        palette.danger
                    },
                    fontSize = 19.sp,
                    lineHeight = 23.sp,
                    fontWeight = FontWeight.ExtraBold,
                    textAlign = TextAlign.Center,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
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
            .padding(
                start = 3.dp,
                end = 3.dp,
                top = 2.dp,
            ),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(
                        width = 4.dp,
                        height = 22.dp,
                    )
                    .clip(RoundedCornerShape(999.dp))
                    .background(
                        Brush.verticalGradient(
                            listOf(
                                palette.accent,
                                palette.accentSecondary,
                            )
                        )
                    )
            )

            Text(
                title,
                color = if (palette.sunsetBackground) {
                    Color.White
                } else {
                    palette.textStrong
                },
                fontFamily = FontFamily.SansSerif,
                fontSize = 22.sp,
                lineHeight = 28.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = (-0.45).sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }

        if (!trailing.isNullOrBlank()) {
            Text(
                trailing,
                color = if (palette.sunsetBackground) {
                    palette.accentSecondary
                } else {
                    palette.accent
                },
                fontSize = 12.5.sp,
                lineHeight = 17.sp,
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
    BoxWithConstraints(
        modifier = Modifier.fillMaxWidth(),
    ) {
        val visibleItems = items.take(4)
        val useTwoColumnGrid = maxWidth < 390.dp &&
            visibleItems.size > 2

        if (useTwoColumnGrid) {
            Column(
                verticalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                visibleItems.chunked(2).forEach { rowItems ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(9.dp),
                    ) {
                        rowItems.forEach { item ->
                            ReferenceActionTile(
                                item = item,
                                palette = palette,
                                modifier = Modifier.weight(1f),
                            )
                        }

                        if (rowItems.size == 1) {
                            Spacer(
                                modifier = Modifier.weight(1f),
                            )
                        }
                    }
                }
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                visibleItems.forEach { item ->
                    ReferenceActionTile(
                        item = item,
                        palette = palette,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
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
                modifier = Modifier.size(92.dp),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    title,
                    color = palette.textStrong,
                    fontSize = 18.sp,
                    lineHeight = 22.sp,
                    fontWeight = FontWeight.ExtraBold,
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
                        fontSize = 11.5.sp,
                        lineHeight = 15.sp,
                        fontWeight = FontWeight.Medium,
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

        if (
            primaryActionLabel.isNotBlank() ||
            secondaryActionLabel.isNotBlank()
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                if (primaryActionLabel.isNotBlank()) {
                    ReferenceGlassButton(
                        text = primaryActionLabel,
                        palette = palette,
                        accent = true,
                        onClick = onPrimaryAction,
                        enabled = primaryActionEnabled,
                        modifier = Modifier.weight(1f),
                    )
                }
                if (secondaryActionLabel.isNotBlank()) {
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
    }
}

@Composable
fun ReferenceScheduleCard(
    time: String,
    customerName: String,
    badge: String,
    lines: List<String>,
    palette: ReferenceDashboardPalette,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    ReferenceGlassPanel(
        modifier = modifier.fillMaxWidth(),
        palette = palette,
        strong = false,
        contentPadding = PaddingValues(
            horizontal = 14.dp,
            vertical = 14.dp,
        ),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(3.dp)
                .clip(RoundedCornerShape(999.dp))
                .background(
                    Brush.horizontalGradient(
                        listOf(
                            palette.accent.copy(alpha = 0.24f),
                            palette.accent,
                            palette.accentSecondary.copy(alpha = 0.54f),
                            Color.Transparent,
                        )
                    )
                )
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(54.dp)
                    .shadow(
                        elevation = 8.dp,
                        shape = CircleShape,
                        ambientColor = palette.accent.copy(alpha = 0.16f),
                        spotColor = palette.accentSecondary.copy(alpha = 0.14f),
                        clip = false,
                    )
                    .clip(CircleShape)
                    .background(
                        Brush.linearGradient(
                            if (palette.darkSurface) {
                                listOf(
                                    palette.accent.copy(alpha = 0.18f),
                                    Color.White.copy(alpha = 0.08f),
                                    palette.accentSecondary.copy(alpha = 0.12f),
                                )
                            } else {
                                listOf(
                                    Color.White.copy(alpha = 0.92f),
                                    palette.accentSoft.copy(alpha = 0.20f),
                                    Color.White.copy(alpha = 0.72f),
                                )
                            }
                        )
                    )
                    .border(
                        BorderStroke(
                            1.2.dp,
                            Brush.linearGradient(
                                listOf(
                                    Color.White.copy(
                                        alpha = if (
                                            palette.darkSurface
                                        ) 0.34f else 0.96f
                                    ),
                                    palette.accent.copy(alpha = 0.42f),
                                    palette.accentSecondary.copy(alpha = 0.30f),
                                )
                            ),
                        ),
                        CircleShape,
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    customerName.take(2),
                    color = palette.textStrong,
                    fontWeight = FontWeight.ExtraBold,
                    fontSize = 14.sp,
                    maxLines = 1,
                )
            }

            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        time,
                        color = palette.textStrong,
                        fontSize = 22.sp,
                        lineHeight = 26.sp,
                        fontWeight = FontWeight.ExtraBold,
                        maxLines = 1,
                    )
                    ReferencePill(
                        text = badge,
                        palette = palette,
                    )
                }

                Text(
                    customerName,
                    color = palette.textStrong,
                    fontSize = 15.sp,
                    lineHeight = 19.sp,
                    fontWeight = FontWeight.ExtraBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )

                lines.take(2).forEach { line ->
                    Text(
                        line,
                        color = palette.textMuted,
                        fontSize = 12.5.sp,
                        lineHeight = 16.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }

            ReferenceGlassButton(
                text = "상세",
                palette = palette,
                onClick = onClick,
                enabled = enabled,
                accent = true,
                compact = true,
            )
        }
    }
}

@Composable
fun ReferenceBottomNavigation(
    items: List<ReferenceBottomItem>,
    palette: ReferenceDashboardPalette,
) {
    val shape = RoundedCornerShape(34.dp)

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(
                elevation = 14.dp,
                shape = shape,
                ambientColor = palette.accent.copy(
                    alpha = if (palette.darkSurface) 0.24f else 0.12f
                ),
                spotColor = palette.accentSecondary.copy(
                    alpha = if (palette.darkSurface) 0.22f else 0.10f
                ),
                clip = false,
            )
            .clip(shape)
            .background(
                if (palette.darkSurface) {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.12f),
                            Color(0xFF0A4D68).copy(alpha = 0.82f),
                            Color(0xFF06364E).copy(alpha = 0.76f),
                        )
                    )
                } else {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.88f),
                            Color.White.copy(alpha = 0.70f),
                            palette.accentSoft.copy(alpha = 0.13f),
                        )
                    )
                }
            )
            .border(
                BorderStroke(
                    1.1.dp,
                    Color.White.copy(
                        alpha = if (
                            palette.darkSurface
                        ) 0.26f else 0.88f
                    ),
                ),
                shape,
            )
            .padding(5.dp),
        horizontalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        items.take(5).forEach { item ->
            val interactionSource = remember {
                MutableInteractionSource()
            }

            Column(
                modifier = Modifier
                    .weight(1f)
                    .height(66.dp)
                    .clip(RoundedCornerShape(21.dp))
                    .graphicsLayer {
                        alpha = if (item.enabled) 1f else 0.58f
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
                            if (palette.darkSurface) {
                                Brush.verticalGradient(
                                    listOf(
                                        palette.accent.copy(alpha = 0.24f),
                                        Color.White.copy(alpha = 0.07f),
                                    )
                                )
                            } else {
                                Brush.verticalGradient(
                                    listOf(
                                        Color.White.copy(alpha = 0.96f),
                                        palette.accentSoft.copy(alpha = 0.18f),
                                    )
                                )
                            }
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
                    modifier = Modifier.size(25.dp),
                )

                Text(
                    item.label,
                    modifier = Modifier.padding(top = 2.dp),
                    color = if (item.selected) {
                        palette.accent
                    } else {
                        palette.textMuted
                    },
                    fontSize = 12.sp,
                    lineHeight = 15.sp,
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
                            .padding(top = 3.dp)
                            .size(
                                width = 34.dp,
                                height = 3.dp,
                            )
                            .clip(RoundedCornerShape(999.dp))
                            .background(
                                Brush.horizontalGradient(
                                    listOf(
                                        palette.accent.copy(alpha = 0.42f),
                                        palette.accent,
                                        palette.accentSecondary.copy(
                                            alpha = 0.56f
                                        ),
                                    )
                                )
                            )
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
    val shape = if (danger) {
        RoundedCornerShape(24.dp)
    } else {
        ReferenceWaterDropPanelShape
    }

    val shadowAlpha = when {
        danger -> 0.15f
        palette.darkSurface && strong -> 0.24f
        palette.darkSurface -> 0.18f
        strong -> 0.10f
        else -> 0.07f
    }

    val borderBrush = if (danger) {
        Brush.linearGradient(
            listOf(
                palette.danger,
                palette.danger.copy(alpha = 0.74f),
            )
        )
    } else if (palette.darkSurface) {
        Brush.linearGradient(
            listOf(
                Color.White.copy(alpha = 0.34f),
                palette.accent.copy(alpha = 0.30f),
                palette.accentSecondary.copy(alpha = 0.22f),
                Color.White.copy(alpha = 0.14f),
            )
        )
    } else {
        Brush.linearGradient(
            listOf(
                Color.White.copy(alpha = 0.98f),
                palette.accent.copy(alpha = 0.24f),
                palette.accentSecondary.copy(alpha = 0.16f),
                Color.White.copy(alpha = 0.90f),
            )
        )
    }

    val surfaceBrush = when {
        danger -> Brush.verticalGradient(
            listOf(
                Color.White.copy(alpha = 0.97f),
                Color.White.copy(alpha = 0.93f),
            )
        )

        palette.darkSurface -> Brush.verticalGradient(
            listOf(
                Color.White.copy(
                    alpha = if (strong) 0.12f else 0.08f
                ),
                Color(0xFF0A536F).copy(
                    alpha = if (strong) 0.78f else 0.66f
                ),
                Color(0xFF063A54).copy(
                    alpha = if (strong) 0.74f else 0.62f
                ),
            )
        )

        else -> Brush.verticalGradient(
            listOf(
                Color.White.copy(
                    alpha = if (strong) 0.82f else 0.74f
                ),
                Color.White.copy(
                    alpha = if (strong) 0.64f else 0.56f
                ),
                palette.accentSoft.copy(
                    alpha = if (strong) 0.10f else 0.065f
                ),
            )
        )
    }

    Column(
        modifier = modifier
            .shadow(
                elevation = when {
                    danger -> 5.dp
                    strong -> 12.dp
                    else -> 7.dp
                },
                shape = shape,
                ambientColor = if (danger) {
                    palette.danger.copy(alpha = 0.16f)
                } else {
                    palette.accent.copy(alpha = shadowAlpha)
                },
                spotColor = if (danger) {
                    palette.danger.copy(alpha = 0.18f)
                } else {
                    palette.accentSecondary.copy(
                        alpha = shadowAlpha * 0.90f
                    )
                },
                clip = false,
            )
            .clip(shape)
            .background(surfaceBrush)
            .drawBehind {
                if (!danger) {
                    drawLine(
                        color = Color.White.copy(
                            alpha = if (
                                palette.darkSurface
                            ) {
                                if (strong) 0.46f else 0.30f
                            } else {
                                if (strong) 0.86f else 0.70f
                            }
                        ),
                        start = Offset(
                            x = size.width * 0.10f,
                            y = 1.5.dp.toPx(),
                        ),
                        end = Offset(
                            x = size.width * 0.78f,
                            y = 1.5.dp.toPx(),
                        ),
                        strokeWidth = 1.1.dp.toPx(),
                        cap = StrokeCap.Round,
                    )

                    drawOval(
                        color = palette.accent.copy(
                            alpha = if (
                                palette.darkSurface
                            ) 0.06f else 0.025f
                        ),
                        topLeft = Offset(
                            x = size.width * 0.70f,
                            y = size.height * 0.67f,
                        ),
                        size = Size(
                            width = size.width * 0.36f,
                            height = size.height * 0.32f,
                        ),
                    )

                    drawLine(
                        color = palette.accentSecondary.copy(
                            alpha = if (
                                palette.darkSurface
                            ) 0.10f else 0.055f
                        ),
                        start = Offset(
                            x = size.width * 0.68f,
                            y = size.height - 1.6.dp.toPx(),
                        ),
                        end = Offset(
                            x = size.width * 0.94f,
                            y = size.height - 1.6.dp.toPx(),
                        ),
                        strokeWidth = 1.dp.toPx(),
                        cap = StrokeCap.Round,
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
    danger: Boolean = false,
    compact: Boolean = false,
) {
    val shape = RoundedCornerShape(999.dp)
    val interactionSource = remember { MutableInteractionSource() }

    val isTechnicianNeutral =
        palette.sunsetBackground && !accent && !danger

    val backgroundBrush = when {
        danger -> Brush.linearGradient(
            listOf(
                Color(0xFF9E332C),
                Color(0xFFD4573A),
                Color(0xFFB84131),
            )
        )

        accent -> Brush.linearGradient(
            listOf(
                palette.accent,
                palette.accentSecondary,
                palette.accent.copy(alpha = 0.82f),
            )
        )

        isTechnicianNeutral -> Brush.linearGradient(
            listOf(
                Color(0xFFFFFCF7),
                Color(0xFFFFF3E1),
                Color(0xFFFFD9A5),
            )
        )

        else -> Brush.linearGradient(
            listOf(
                Color.White.copy(alpha = if (enabled) 0.30f else 0.10f),
                palette.accentSoft.copy(alpha = if (enabled) 0.20f else 0.08f),
                palette.accentSecondary.copy(alpha = if (enabled) 0.12f else 0.05f),
                Color.White.copy(alpha = if (enabled) 0.16f else 0.06f),
            )
        )
    }

    val borderBrush = when {
        danger -> Brush.linearGradient(
            listOf(
                Color.White.copy(alpha = 0.96f),
                Color(0xFFFFB29A),
                palette.danger,
                Color.White.copy(alpha = 0.82f),
            )
        )

        isTechnicianNeutral -> Brush.linearGradient(
            listOf(
                Color.White,
                Color(0xFFF59E0B).copy(alpha = 0.86f),
                Color(0xFF334E68).copy(alpha = 0.54f),
                Color.White.copy(alpha = 0.94f),
            )
        )

        else -> Brush.linearGradient(
            listOf(
                Color.White.copy(alpha = if (enabled) 0.98f else 0.42f),
                palette.accent.copy(alpha = if (accent) 0.96f else 0.78f),
                palette.accentSecondary.copy(alpha = if (accent) 0.90f else 0.66f),
                Color.White.copy(alpha = if (enabled) 0.84f else 0.30f),
            )
        )
    }

    val shadowBase = when {
        danger -> palette.danger
        isTechnicianNeutral -> Color(0xFFF59E0B)
        else -> palette.accent
    }

    Row(
        modifier = modifier
            .shadow(
                elevation = when {
                    danger -> 12.dp
                    accent -> 13.dp
                    isTechnicianNeutral -> 10.dp
                    else -> 7.dp
                },
                shape = shape,
                ambientColor = shadowBase.copy(
                    alpha = if (enabled) 0.28f else 0.08f
                ),
                spotColor = shadowBase.copy(
                    alpha = if (enabled) 0.24f else 0.06f
                ),
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
            .background(backgroundBrush)
            .drawBehind {
                drawLine(
                    color = Color.White.copy(
                        alpha = if (enabled) 0.84f else 0.34f
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
                    width = when {
                        danger -> 1.9.dp
                        accent -> 1.7.dp
                        isTechnicianNeutral -> 1.7.dp
                        else -> 1.4.dp
                    },
                    brush = borderBrush,
                ),
                shape,
            )
            .heightIn(min = if (compact) 48.dp else 56.dp)
            .padding(
                horizontal = if (compact) 13.dp else 17.dp,
                vertical = if (compact) 8.dp else 12.dp,
            ),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = if (enabled) {
                text + "  \u203A"
            } else {
                text
            },
            color = when {
                !enabled -> palette.textMuted
                danger -> Color.White
                accent -> Color.White
                isTechnicianNeutral -> Color(0xFF20384C)
                else -> palette.accent
            },
            fontSize = if (compact) 13.sp else 14.sp,
            lineHeight = if (compact) 16.sp else 18.sp,
            fontWeight = FontWeight.ExtraBold,
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
    val shape = RoundedCornerShape(999.dp)

    Row(
        modifier = Modifier
            .shadow(
                elevation = 5.dp,
                shape = shape,
                ambientColor = palette.accent.copy(alpha = 0.20f),
                spotColor = palette.accentSecondary.copy(alpha = 0.16f),
                clip = false,
            )
            .clip(shape)
            .background(
                if (palette.darkSurface) {
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = 0.10f),
                            palette.accent.copy(alpha = 0.12f),
                            Color.White.copy(alpha = 0.05f),
                        )
                    )
                } else {
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = 0.82f),
                            Color.White.copy(alpha = 0.58f),
                            palette.accentSoft.copy(alpha = 0.12f),
                        )
                    )
                }
            )
            .border(
                BorderStroke(
                    1.15.dp,
                    if (palette.darkSurface) {
                        Color.White.copy(alpha = 0.30f)
                    } else {
                        palette.accent.copy(alpha = 0.50f)
                    },
                ),
                shape,
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
            color = if (palette.darkSurface) {
                palette.textStrong
            } else {
                palette.accent
            },
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
        )

        Text(
            "⌄",
            color = if (palette.darkSurface) {
                palette.textStrong.copy(alpha = 0.80f)
            } else {
                palette.accent.copy(alpha = 0.82f)
            },
            fontSize = 13.sp,
            lineHeight = 13.sp,
            fontWeight = FontWeight.Bold,
        )
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
            .size(48.dp)
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
                        Color.White.copy(
                            alpha = if (
                                palette.darkSurface
                            ) 0.12f else 0.72f
                        ),
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
                        color = if (palette.darkSurface) {
                            Color.White
                        } else {
                            palette.textStrong
                        },
                        style = stroke,
                    )
                    drawLine(
                        color = if (palette.darkSurface) {
                            Color.White
                        } else {
                            palette.textStrong
                        },
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
                        color = if (palette.darkSurface) {
                            Color.White
                        } else {
                            palette.textStrong
                        },
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
                        color = if (palette.darkSurface) {
                            Color.White
                        } else {
                            palette.textStrong
                        },
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
                        color = if (palette.darkSurface) {
                            Color.White
                        } else {
                            palette.textStrong
                        },
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
                        color = if (palette.darkSurface) {
                            Color.White
                        } else {
                            palette.textStrong
                        },
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
                        color = if (palette.darkSurface) {
                            Color.White
                        } else {
                            palette.textStrong
                        },
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
                        color = if (palette.darkSurface) {
                            Color.White
                        } else {
                            palette.textStrong
                        },
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
    val tileShape = RoundedCornerShape(25.dp)

    Column(
        modifier = modifier
            .height(124.dp)
            .shadow(
                elevation = if (palette.darkSurface) 9.dp else 7.dp,
                shape = tileShape,
                ambientColor = palette.accent.copy(
                    alpha = if (palette.darkSurface) 0.18f else 0.10f
                ),
                spotColor = palette.accentSecondary.copy(
                    alpha = if (palette.darkSurface) 0.16f else 0.08f
                ),
                clip = false,
            )
            .clip(tileShape)
            .background(
                if (palette.darkSurface) {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.105f),
                            Color(0xFF0A4B66).copy(alpha = 0.72f),
                            Color(0xFF073A55).copy(alpha = 0.66f),
                        )
                    )
                } else {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = 0.91f),
                            Color.White.copy(alpha = 0.72f),
                            palette.accentSoft.copy(alpha = 0.11f),
                        )
                    )
                }
            )
            .border(
                BorderStroke(
                    1.1.dp,
                    if (palette.darkSurface) {
                        Color.White.copy(alpha = 0.24f)
                    } else {
                        Color.White.copy(alpha = 0.88f)
                    },
                ),
                tileShape,
            )
            .padding(
                horizontal = 6.dp,
                vertical = 10.dp,
            ),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        Box(
            modifier = Modifier
                .size(
                    width = 30.dp,
                    height = 3.dp,
                )
                .clip(RoundedCornerShape(999.dp))
                .background(
                    Brush.horizontalGradient(
                        listOf(
                            palette.accent.copy(alpha = 0.28f),
                            palette.accent.copy(alpha = 0.92f),
                            palette.accentSecondary.copy(alpha = 0.52f),
                        )
                    )
                )
        )

        Box(
            modifier = Modifier
                .size(43.dp)
                .clip(CircleShape)
                .background(
                    if (palette.darkSurface) {
                        Color.White.copy(alpha = 0.10f)
                    } else {
                        Color.White.copy(alpha = 0.76f)
                    }
                )
                .border(
                    BorderStroke(
                        1.dp,
                        Color.White.copy(
                            alpha = if (
                                palette.darkSurface
                            ) 0.22f else 0.94f
                        ),
                    ),
                    CircleShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(item.iconRes),
                contentDescription = item.label,
                modifier = Modifier.size(29.dp),
            )
        }

        Text(
            item.label,
            color = palette.textMuted,
            fontSize = 11.5.sp,
            lineHeight = 14.5.sp,
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
            fontSize = 15.5.sp,
            lineHeight = 19.sp,
            fontWeight = FontWeight.ExtraBold,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun ReferenceActionTile(
    item: ReferenceActionItem,
    palette: ReferenceDashboardPalette,
    modifier: Modifier = Modifier,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val shape = RoundedCornerShape(25.dp)
    val tagModifier = if (item.testTag.isNullOrBlank()) {
        Modifier
    } else {
        Modifier.testTag(item.testTag)
    }

    Column(
        modifier = modifier
            .then(tagModifier)
            .height(134.dp)
            .shadow(
                elevation = if (item.enabled) 8.dp else 2.dp,
                shape = shape,
                ambientColor = palette.accent.copy(
                    alpha = if (item.enabled) {
                        if (palette.darkSurface) 0.18f else 0.10f
                    } else {
                        0.03f
                    }
                ),
                spotColor = palette.accentSecondary.copy(
                    alpha = if (item.enabled) {
                        if (palette.darkSurface) 0.16f else 0.08f
                    } else {
                        0.02f
                    }
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
                if (palette.darkSurface) {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(
                                alpha = if (item.enabled) 0.11f else 0.06f
                            ),
                            Color(0xFF0A506B).copy(
                                alpha = if (item.enabled) 0.70f else 0.42f
                            ),
                            Color(0xFF063850).copy(
                                alpha = if (item.enabled) 0.66f else 0.36f
                            ),
                        )
                    )
                } else {
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(
                                alpha = if (item.enabled) 0.92f else 0.76f
                            ),
                            Color.White.copy(
                                alpha = if (item.enabled) 0.72f else 0.58f
                            ),
                            palette.accentSoft.copy(
                                alpha = if (item.enabled) 0.10f else 0.04f
                            ),
                        )
                    )
                }
            )
            .border(
                BorderStroke(
                    width = 1.1.dp,
                    brush = Brush.linearGradient(
                        listOf(
                            Color.White.copy(
                                alpha = if (
                                    palette.darkSurface
                                ) 0.26f else 0.94f
                            ),
                            palette.accent.copy(
                                alpha = if (item.enabled) 0.30f else 0.12f
                            ),
                            Color.White.copy(
                                alpha = if (
                                    palette.darkSurface
                                ) 0.14f else 0.82f
                            ),
                        )
                    ),
                ),
                shape,
            )
            .padding(
                horizontal = 6.dp,
                vertical = 9.dp,
            ),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .size(
                    width = 34.dp,
                    height = 3.dp,
                )
                .clip(RoundedCornerShape(999.dp))
                .background(
                    if (item.enabled) {
                        Brush.horizontalGradient(
                            listOf(
                                palette.accent.copy(alpha = 0.30f),
                                palette.accent.copy(alpha = 0.92f),
                                palette.accentSecondary.copy(alpha = 0.52f),
                            )
                        )
                    } else {
                        Brush.horizontalGradient(
                            listOf(
                                palette.textMuted.copy(alpha = 0.10f),
                                palette.textMuted.copy(alpha = 0.22f),
                            )
                        )
                    }
                )
        )

        Box(
            modifier = Modifier
                .size(52.dp)
                .clip(CircleShape)
                .background(
                    if (palette.darkSurface) {
                        Color.White.copy(alpha = 0.10f)
                    } else {
                        Color.White.copy(alpha = 0.76f)
                    }
                )
                .border(
                    BorderStroke(
                        1.dp,
                        Color.White.copy(
                            alpha = if (
                                palette.darkSurface
                            ) 0.24f else 0.94f
                        ),
                    ),
                    CircleShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(item.iconRes),
                contentDescription = item.label,
                modifier = Modifier.size(32.dp),
                alpha = if (item.enabled) 1f else 0.58f,
            )
        }

        Text(
            text = item.label,
            modifier = Modifier.padding(top = 6.dp),
            color = if (item.enabled) {
                palette.textStrong
            } else {
                palette.textMuted
            },
            fontSize = 12.5.sp,
            lineHeight = 16.sp,
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
                fontSize = 10.5.sp,
                lineHeight = 13.5.sp,
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
fun ReferencePearlBackground(
    palette: ReferenceDashboardPalette,
    @DrawableRes backgroundRes: Int? = null,
    imageAlpha: Float = 0.54f,
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    val baseGradient = when {
        palette.sunsetBackground -> Brush.verticalGradient(
            listOf(
                Color(0xFF0A2238),
                Color(0xFF12344E),
                Color(0xFF3C3B43),
                Color(0xFF76503E),
                Color(0xFF9A5A37),
            )
        )

        palette.darkSurface -> Brush.verticalGradient(
            listOf(
                Color(0xFF043A55),
                Color(0xFF05324A),
                palette.backgroundStart,
                Color(0xFF031F32),
            )
        )

        else -> Brush.verticalGradient(
            listOf(
                Color(0xFF4FAFE8),
                Color(0xFF9FDCF5),
                Color(0xFFEAF8FF),
                palette.backgroundEnd,
            )
        )
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(baseGradient),
    ) {
        backgroundRes?.let { resource ->
            Image(
                painter = painterResource(resource),
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
                alpha = imageAlpha.coerceIn(0.0f, 1.0f),
            )
        }

        if (palette.sunsetBackground) {
            // Navy veil: keeps the technician screen professional and
            // prevents the water texture from looking like the customer app.
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.verticalGradient(
                            listOf(
                                Color(0xFF071C2F).copy(alpha = 0.52f),
                                Color(0xFF0E2A41).copy(alpha = 0.30f),
                                Color(0xFF382E32).copy(alpha = 0.18f),
                                Color(0xFF5C392E).copy(alpha = 0.24f),
                            )
                        )
                    )
            )

            // Warm sunset glow from the right side.
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.radialGradient(
                            colors = listOf(
                                Color(0xFFFFA33A).copy(alpha = 0.62f),
                                Color(0xFFF07A2D).copy(alpha = 0.28f),
                                Color.Transparent,
                            ),
                            center = Offset(980f, 660f),
                            radius = 760f,
                        )
                    )
            )

            // Secondary amber reflection near the lower-right area.
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.radialGradient(
                            colors = listOf(
                                Color(0xFFFFB15A).copy(alpha = 0.28f),
                                Color(0xFFE9772F).copy(alpha = 0.14f),
                                Color.Transparent,
                            ),
                            center = Offset(900f, 1480f),
                            radius = 780f,
                        )
                    )
            )

            // Cool navy light at the top-left preserves WaterBridge identity.
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.radialGradient(
                            colors = listOf(
                                Color(0xFF2A5D82).copy(alpha = 0.32f),
                                Color.Transparent,
                            ),
                            center = Offset(120f, 110f),
                            radius = 680f,
                        )
                    )
            )
        } else {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        if (palette.darkSurface) {
                            Brush.verticalGradient(
                                listOf(
                                    Color(0xFF03283D).copy(alpha = 0.36f),
                                    Color(0xFF04334A).copy(alpha = 0.20f),
                                    Color(0xFF021F32).copy(alpha = 0.56f),
                                )
                            )
                        } else {
                            Brush.verticalGradient(
                                listOf(
                                    Color(0xFF1689D1).copy(alpha = 0.10f),
                                    Color.White.copy(alpha = 0.05f),
                                    Color.White.copy(alpha = 0.12f),
                                    Color(0xFFEAF8FF).copy(alpha = 0.24f),
                                )
                            )
                        }
                    )
            )

            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.radialGradient(
                            colors = listOf(
                                if (palette.darkSurface) {
                                    palette.accent.copy(alpha = 0.12f)
                                } else {
                                    Color.White.copy(alpha = 0.36f)
                                },
                                Color.Transparent,
                            ),
                            center = Offset(180f, 140f),
                            radius = 820f,
                        )
                    )
            )

            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.radialGradient(
                            colors = listOf(
                                palette.accentSecondary.copy(
                                    alpha = if (palette.darkSurface) {
                                        0.09f
                                    } else {
                                        0.06f
                                    }
                                ),
                                Color.Transparent,
                            ),
                            center = Offset(880f, 1380f),
                            radius = 920f,
                        )
                    )
            )
        }

        Canvas(
            modifier = Modifier.fillMaxSize(),
        ) {
            val lineColor = when {
                palette.sunsetBackground ->
                    Color.White.copy(alpha = 0.075f)

                palette.darkSurface ->
                    Color.White.copy(alpha = 0.045f)

                else ->
                    Color.White.copy(alpha = 0.18f)
            }

            val accentLine = if (palette.sunsetBackground) {
                Color(0xFFFFA33A).copy(alpha = 0.16f)
            } else {
                palette.accent.copy(
                    alpha = if (palette.darkSurface) 0.055f else 0.07f
                )
            }

            drawArc(
                color = lineColor,
                startAngle = 195f,
                sweepAngle = 115f,
                useCenter = false,
                topLeft = Offset(
                    x = -size.width * 0.18f,
                    y = size.height * 0.12f,
                ),
                size = Size(
                    width = size.width * 0.86f,
                    height = size.width * 0.48f,
                ),
                style = Stroke(
                    width = 1.4.dp.toPx(),
                    cap = StrokeCap.Round,
                ),
            )

            drawArc(
                color = accentLine,
                startAngle = 20f,
                sweepAngle = 125f,
                useCenter = false,
                topLeft = Offset(
                    x = size.width * 0.50f,
                    y = size.height * 0.42f,
                ),
                size = Size(
                    width = size.width * 0.72f,
                    height = size.width * 0.54f,
                ),
                style = Stroke(
                    width = 1.2.dp.toPx(),
                    cap = StrokeCap.Round,
                ),
            )

            drawCircle(
                color = Color.White.copy(
                    alpha = when {
                        palette.sunsetBackground -> 0.07f
                        palette.darkSurface -> 0.035f
                        else -> 0.12f
                    }
                ),
                radius = size.minDimension * 0.075f,
                center = Offset(
                    x = size.width * 0.88f,
                    y = size.height * 0.18f,
                ),
                style = Stroke(width = 1.dp.toPx()),
            )

            drawCircle(
                color = if (palette.sunsetBackground) {
                    Color(0xFFFFA33A).copy(alpha = 0.12f)
                } else {
                    palette.accentSecondary.copy(
                        alpha = if (palette.darkSurface) 0.045f else 0.055f
                    )
                },
                radius = size.minDimension * 0.055f,
                center = Offset(
                    x = size.width * 0.12f,
                    y = size.height * 0.72f,
                ),
                style = Stroke(width = 1.dp.toPx()),
            )
        }

        content()
    }
}
