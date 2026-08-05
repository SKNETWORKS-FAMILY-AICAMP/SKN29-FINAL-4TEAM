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
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.ui.theme.Ink400
import com.skn29.watercare.core.ui.theme.Ink600
import com.skn29.watercare.core.ui.theme.Ink900
import com.skn29.watercare.core.ui.theme.Water500
import com.skn29.watercare.core.ui.theme.WaterTokens

enum class LiquidGlassTone {
    CUSTOMER,
    TECHNICIAN,
}

private data class LiquidGlassRolePalette(
    val accent: Color,
    val accentSecondary: Color,
    val accentSoft: Color,
    val textStrong: Color,
    val textMuted: Color,
)

private val CustomerLiquidPalette = LiquidGlassRolePalette(
    accent = Color(0xFF248CFF),
    accentSecondary = Color(0xFF64C9FF),
    accentSoft = Color(0xFFBFEAFF),
    textStrong = Color(0xFF123C61),
    textMuted = Color(0xFF597A94),
)

private val TechnicianLiquidPalette = LiquidGlassRolePalette(
    accent = Color(0xFF0FB9AA),
    accentSecondary = Color(0xFF55E5D5),
    accentSoft = Color(0xFFB9F4EC),
    textStrong = Color(0xFF123F3A),
    textMuted = Color(0xFF577D78),
)

private val LocalLiquidGlassTone = compositionLocalOf {
    LiquidGlassTone.CUSTOMER
}

@Composable
fun LiquidGlassToneProvider(
    tone: LiquidGlassTone,
    content: @Composable () -> Unit,
) {
    CompositionLocalProvider(
        LocalLiquidGlassTone provides tone,
        content = content,
    )
}

@Composable
private fun liquidPalette(): LiquidGlassRolePalette =
    when (LocalLiquidGlassTone.current) {
        LiquidGlassTone.CUSTOMER -> CustomerLiquidPalette
        LiquidGlassTone.TECHNICIAN -> TechnicianLiquidPalette
    }

private val LiquidWaterDropPanelShape = RoundedCornerShape(
    topStart = 34.dp,
    topEnd = 48.dp,
    bottomEnd = 28.dp,
    bottomStart = 42.dp,
)

private val LiquidWaterDropControlShape = RoundedCornerShape(999.dp)

private val LiquidWaterDropTileShape = RoundedCornerShape(
    topStart = 24.dp,
    topEnd = 34.dp,
    bottomEnd = 20.dp,
    bottomStart = 30.dp,
)

@Composable
fun LiquidGlassPanel(
    modifier: Modifier = Modifier,
    strong: Boolean = false,
    danger: Boolean = false,
    contentPadding: PaddingValues = PaddingValues(18.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    val palette = liquidPalette()
    val shape = if (danger) {
        RoundedCornerShape(24.dp)
    } else {
        LiquidWaterDropPanelShape
    }

    val surfaceAlpha = if (strong) 0.22f else 0.14f
    val accentAlpha = if (strong) 0.17f else 0.10f
    val glowAlpha = if (strong) 0.34f else 0.22f

    val fillBrush = if (danger) {
        Brush.verticalGradient(
            listOf(
                Color.White.copy(alpha = 0.96f),
                Color.White.copy(alpha = 0.90f),
            )
        )
    } else {
        Brush.verticalGradient(
            listOf(
                Color.White.copy(alpha = surfaceAlpha),
                palette.accentSoft.copy(alpha = accentAlpha),
                Color.White.copy(alpha = 0.055f),
                Color.Transparent,
                palette.accentSecondary.copy(
                    alpha = accentAlpha * 0.62f
                ),
                Color.White.copy(alpha = surfaceAlpha * 0.58f),
            )
        )
    }

    val borderBrush = if (danger) {
        Brush.linearGradient(
            listOf(
                WaterTokens.Danger,
                WaterTokens.Danger,
            )
        )
    } else {
        Brush.linearGradient(
            listOf(
                Color.White.copy(alpha = 0.99f),
                palette.accent.copy(alpha = 0.90f),
                palette.accentSecondary.copy(alpha = 0.80f),
                Color.White.copy(alpha = 0.92f),
            )
        )
    }

    Column(
        modifier = modifier
            .shadow(
                elevation = if (danger) {
                    5.dp
                } else if (strong) {
                    13.dp
                } else {
                    8.dp
                },
                shape = shape,
                ambientColor = if (danger) {
                    WaterTokens.Danger.copy(alpha = 0.16f)
                } else {
                    palette.accent.copy(alpha = glowAlpha)
                },
                spotColor = if (danger) {
                    WaterTokens.Danger.copy(alpha = 0.18f)
                } else {
                    palette.accentSecondary.copy(
                        alpha = glowAlpha * 0.90f
                    )
                },
                clip = false,
            )
            .clip(shape)
            .background(fillBrush)
            .drawBehind {
                if (!danger) {
                    drawOval(
                        color = Color.White.copy(
                            alpha = if (strong) 0.40f else 0.28f
                        ),
                        topLeft = Offset(
                            x = size.width * 0.07f,
                            y = size.height * 0.045f,
                        ),
                        size = Size(
                            width = size.width * 0.36f,
                            height = size.height * 0.16f,
                        ),
                    )

                    drawOval(
                        color = palette.accent.copy(
                            alpha = if (strong) 0.14f else 0.09f
                        ),
                        topLeft = Offset(
                            x = size.width * 0.63f,
                            y = size.height * 0.64f,
                        ),
                        size = Size(
                            width = size.width * 0.44f,
                            height = size.height * 0.43f,
                        ),
                    )

                    drawLine(
                        color = Color.White.copy(
                            alpha = if (strong) 0.68f else 0.48f
                        ),
                        start = Offset(
                            x = size.width * 0.12f,
                            y = 2.dp.toPx(),
                        ),
                        end = Offset(
                            x = size.width * 0.76f,
                            y = 2.dp.toPx(),
                        ),
                        strokeWidth = 1.4.dp.toPx(),
                        cap = StrokeCap.Round,
                    )
                }
            }
            .border(
                BorderStroke(
                    width = if (danger) 1.5.dp else 2.dp,
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
fun LiquidGlassButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    accent: Boolean = false,
    leadingIcon: String? = null,
    compact: Boolean = false,
) {
    val palette = liquidPalette()
    val shape = LiquidWaterDropControlShape
    val interactionSource = remember { MutableInteractionSource() }

    val primaryAlpha = if (enabled) 0.98f else 0.30f
    val secondaryAlpha = if (enabled) 0.88f else 0.22f
    val neutralAlpha = if (enabled) 0.24f else 0.07f
    val glowAlpha = if (accent) 0.46f else 0.28f

    Row(
        modifier = modifier
            .shadow(
                elevation = if (accent) 15.dp else 8.dp,
                shape = shape,
                ambientColor = palette.accent.copy(alpha = glowAlpha),
                spotColor = palette.accentSecondary.copy(
                    alpha = glowAlpha * 0.92f
                ),
                clip = false,
            )
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
                            palette.accent.copy(alpha = primaryAlpha),
                            palette.accentSecondary.copy(
                                alpha = secondaryAlpha
                            ),
                            palette.accent.copy(
                                alpha = primaryAlpha * 0.80f
                            ),
                        )
                    )
                } else {
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = neutralAlpha),
                            palette.accentSoft.copy(alpha = 0.20f),
                            palette.accentSecondary.copy(alpha = 0.13f),
                            Color.Transparent,
                            Color.White.copy(alpha = neutralAlpha * 0.55f),
                        )
                    )
                }
            )
            .drawBehind {
                drawOval(
                    color = Color.White.copy(
                        alpha = if (accent) 0.40f else 0.30f
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
                        alpha = if (accent) 0.90f else 0.68f
                    ),
                    start = Offset(
                        x = size.width * 0.12f,
                        y = 1.5.dp.toPx(),
                    ),
                    end = Offset(
                        x = size.width * 0.72f,
                        y = 1.5.dp.toPx(),
                    ),
                    strokeWidth = 1.25.dp.toPx(),
                    cap = StrokeCap.Round,
                )
            }
            .border(
                BorderStroke(
                    width = if (accent) 1.7.dp else 1.5.dp,
                    brush = Brush.linearGradient(
                        listOf(
                            Color.White.copy(
                                alpha = if (enabled) 0.99f else 0.42f
                            ),
                            palette.accent.copy(
                                alpha = if (accent) 0.99f else 0.88f
                            ),
                            palette.accentSecondary.copy(
                                alpha = if (accent) 0.94f else 0.76f
                            ),
                            Color.White.copy(
                                alpha = if (enabled) 0.90f else 0.34f
                            ),
                        )
                    ),
                ),
                shape,
            )
            .heightIn(min = if (compact) 40.dp else 54.dp)
            .padding(
                horizontal = if (compact) 14.dp else 18.dp,
                vertical = if (compact) 8.dp else 14.dp,
            ),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (!leadingIcon.isNullOrBlank()) {
            Text(
                leadingIcon,
                modifier = Modifier.padding(end = 8.dp),
                color = if (accent) Color.White else palette.accent,
                style = if (compact) {
                    MaterialTheme.typography.titleSmall
                } else {
                    MaterialTheme.typography.titleMedium
                },
            )
        }

        Text(
            text,
            color = when {
                !enabled -> Ink400
                accent -> Color.White
                else -> palette.accent
            },
            fontWeight = FontWeight.ExtraBold,
            style = if (compact) {
                MaterialTheme.typography.labelMedium
            } else {
                MaterialTheme.typography.labelLarge
            },
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
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
    val palette = liquidPalette()
    val shape = LiquidWaterDropTileShape
    val interactionSource = remember { MutableInteractionSource() }

    Column(
        modifier = modifier
            .shadow(
                elevation = if (enabled) 10.dp else 2.dp,
                shape = shape,
                ambientColor = palette.accent.copy(
                    alpha = if (enabled) 0.30f else 0.06f
                ),
                spotColor = palette.accentSecondary.copy(
                    alpha = if (enabled) 0.26f else 0.05f
                ),
                clip = false,
            )
            .clip(shape)
            .clickable(
                enabled = enabled,
                role = Role.Button,
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick,
            )
            .background(
                Brush.verticalGradient(
                    listOf(
                        Color.White.copy(
                            alpha = if (enabled) 0.26f else 0.07f
                        ),
                        palette.accentSoft.copy(
                            alpha = if (enabled) 0.20f else 0.04f
                        ),
                        palette.accentSecondary.copy(
                            alpha = if (enabled) 0.11f else 0.025f
                        ),
                        Color.Transparent,
                    )
                )
            )
            .drawBehind {
                drawOval(
                    color = Color.White.copy(
                        alpha = if (enabled) 0.36f else 0.08f
                    ),
                    topLeft = Offset(
                        x = size.width * 0.12f,
                        y = size.height * 0.06f,
                    ),
                    size = Size(
                        width = size.width * 0.48f,
                        height = size.height * 0.20f,
                    ),
                )
            }
            .border(
                BorderStroke(
                    1.7.dp,
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(
                                alpha = if (enabled) 0.98f else 0.30f
                            ),
                            palette.accent.copy(
                                alpha = if (enabled) 0.92f else 0.26f
                            ),
                            palette.accentSecondary.copy(
                                alpha = if (enabled) 0.82f else 0.22f
                            ),
                        )
                    ),
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
            color = if (enabled) palette.accent else Ink400,
            fontWeight = FontWeight.ExtraBold,
            style = MaterialTheme.typography.titleSmall,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            subtitle,
            color = if (enabled) palette.textMuted else Ink400,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
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
    val palette = liquidPalette()
    val shape = LiquidWaterDropTileShape

    Column(
        modifier = modifier
            .shadow(
                elevation = 5.dp,
                shape = shape,
                ambientColor = tint.copy(alpha = 0.18f),
                spotColor = palette.accent.copy(alpha = 0.12f),
                clip = false,
            )
            .clip(shape)
            .background(
                Brush.verticalGradient(
                    listOf(
                        Color.White.copy(alpha = 0.24f),
                        tint.copy(alpha = 0.14f),
                        Color.Transparent,
                    )
                )
            )
            .border(
                BorderStroke(
                    1.4.dp,
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = 0.96f),
                            tint.copy(alpha = 0.72f),
                            palette.accentSecondary.copy(alpha = 0.48f),
                        )
                    ),
                ),
                shape,
            )
            .padding(13.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            value,
            color = tint,
            fontWeight = FontWeight.Black,
            style = MaterialTheme.typography.titleMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            label,
            color = palette.textMuted,
            style = MaterialTheme.typography.bodySmall,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
fun LiquidGlassPill(
    text: String,
    modifier: Modifier = Modifier,
    tint: Color = Water500,
) {
    val shape = LiquidWaterDropControlShape

    Text(
        text = text,
        modifier = modifier
            .clip(shape)
            .background(
                Brush.linearGradient(
                    listOf(
                        Color.White.copy(alpha = 0.30f),
                        tint.copy(alpha = 0.18f),
                        Color.Transparent,
                    )
                )
            )
            .border(
                BorderStroke(
                    1.2.dp,
                    Brush.linearGradient(
                        listOf(
                            Color.White.copy(alpha = 0.94f),
                            tint.copy(alpha = 0.68f),
                        )
                    ),
                ),
                shape,
            )
            .padding(horizontal = 12.dp, vertical = 7.dp),
        color = tint,
        fontWeight = FontWeight.ExtraBold,
        style = MaterialTheme.typography.bodySmall,
        maxLines = 2,
        overflow = TextOverflow.Ellipsis,
    )
}
