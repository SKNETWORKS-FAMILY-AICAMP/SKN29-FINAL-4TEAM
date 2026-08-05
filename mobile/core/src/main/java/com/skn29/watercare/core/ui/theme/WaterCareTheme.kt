package com.skn29.watercare.core.ui.theme

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.matchParentSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

object WaterTokens {
    val Water50 = Color(0xFFF2F9FB)
    val Water100 = Color(0xFFDCEEF3)
    val Water300 = Color(0xFF8FC9D8)
    val Water500 = Color(0xFF2E8BA3)
    val Water700 = Color(0xFF1B5A6B)

    val Ink900 = Color(0xFF12262B)
    val Ink600 = Color(0xFF4A6169)
    val Ink400 = Color(0xFF7D9199)

    val GlassFill = Color.White.copy(alpha = 0.55f)
    val GlassFillStrong = Color.White.copy(alpha = 0.72f)
    val GlassBorder = Color.White.copy(alpha = 0.65f)

    val GlassButton = Color.White.copy(alpha = 0.34f)
    val GlassButtonStrong = Color.White.copy(alpha = 0.54f)
    val GlassDisabled = Color.White.copy(alpha = 0.20f)
    val GlassHighlight = Color.White.copy(alpha = 0.90f)

    val PearlBlue = Color(0xFFB8DFFF)
    val PearlLavender = Color(0xFFD9C8FF)
    val PearlPink = Color(0xFFFFD8EE)
    val PearlMint = Color(0xFFBDEFE2)

    val General = Color(0xFF2E8BA3)
    val Caution = Color(0xFFC08A2E)
    val Danger = Color(0xFFC0392B)

    val RadiusCard = 24.dp
    val RadiusControl = 16.dp
    val RadiusPill = 999.dp

    val SpaceXs = 4.dp
    val SpaceSm = 8.dp
    val SpaceMd = 16.dp
    val SpaceLg = 24.dp
    val SpaceXl = 32.dp
}

val Water50 = WaterTokens.Water50
val Water100 = WaterTokens.Water100
val Water300 = WaterTokens.Water300
val Water500 = WaterTokens.Water500
val Water700 = WaterTokens.Water700

val Ink900 = WaterTokens.Ink900
val Ink600 = WaterTokens.Ink600
val Ink400 = WaterTokens.Ink400

val GlassFill = WaterTokens.GlassFill
val GlassFillStrong = WaterTokens.GlassFillStrong
val GlassBorder = WaterTokens.GlassBorder

val WaterGeneral = WaterTokens.General
val WaterCaution = WaterTokens.Caution
val WaterDanger = WaterTokens.Danger

val WaterSky = Water300
val WaterSkyDark = Water500
val WaterAqua = Water300
val WaterSkySoft = Water100

val WaterOrange = Water500
val WaterOrangeDark = Water700
val WaterOrangeSoft = Water100

val WaterBackground = Water50
val WaterCard = GlassFill
val WaterText = Ink900
val WaterSubText = Ink600
val WaterBorder = GlassBorder
val WaterSuccess = WaterGeneral

private val WaterColorScheme = lightColorScheme(
    primary = Water500,
    onPrimary = Color.White,
    primaryContainer = GlassFillStrong,
    onPrimaryContainer = Ink900,
    secondary = Water300,
    onSecondary = Ink900,
    secondaryContainer = GlassFillStrong,
    onSecondaryContainer = Ink900,
    tertiary = Water700,
    onTertiary = Color.White,
    tertiaryContainer = Water100,
    onTertiaryContainer = Water700,
    background = Water50,
    onBackground = Ink900,
    surface = GlassFill,
    onSurface = Ink900,
    surfaceVariant = GlassFillStrong,
    onSurfaceVariant = Ink600,
    outline = GlassBorder,
    outlineVariant = GlassBorder,
    error = WaterDanger,
    onError = Color.White,
    errorContainer = Color.White,
    onErrorContainer = WaterDanger,
    surfaceTint = Color.Transparent,
)

private val WaterTypography = Typography(
    headlineMedium = TextStyle(
        fontSize = 25.sp,
        lineHeight = 34.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    headlineSmall = TextStyle(
        fontSize = 23.sp,
        lineHeight = 32.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    titleLarge = TextStyle(
        fontSize = 19.sp,
        lineHeight = 27.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    titleMedium = TextStyle(
        fontSize = 17.sp,
        lineHeight = 25.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    titleSmall = TextStyle(
        fontSize = 15.sp,
        lineHeight = 23.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    bodyLarge = TextStyle(
        fontSize = 15.sp,
        lineHeight = 24.sp,
        fontWeight = FontWeight.Normal,
    ),
    bodyMedium = TextStyle(
        fontSize = 15.sp,
        lineHeight = 23.sp,
        fontWeight = FontWeight.Normal,
    ),
    bodySmall = TextStyle(
        fontSize = 13.sp,
        lineHeight = 20.sp,
        fontWeight = FontWeight.Normal,
    ),
    labelLarge = TextStyle(
        fontSize = 14.sp,
        lineHeight = 20.sp,
        fontWeight = FontWeight.SemiBold,
    ),
    labelMedium = TextStyle(
        fontSize = 12.sp,
        lineHeight = 18.sp,
        fontWeight = FontWeight.Medium,
    ),
    labelSmall = TextStyle(
        fontSize = 11.sp,
        lineHeight = 17.sp,
        fontWeight = FontWeight.Normal,
    ),
)

private val WaterShapes = Shapes(
    extraSmall = RoundedCornerShape(12.dp),
    small = RoundedCornerShape(WaterTokens.RadiusControl),
    medium = RoundedCornerShape(WaterTokens.RadiusControl),
    large = RoundedCornerShape(WaterTokens.RadiusCard),
    extraLarge = RoundedCornerShape(WaterTokens.RadiusCard),
)

@Composable
fun WaterGradientBackground(
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        Color(0xFFF8FBFF),
                        WaterTokens.Water50,
                        Color(0xFFF7F4FF),
                    ),
                )
            ),
    ) {
        Box(
            modifier = Modifier
                .matchParentSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            WaterTokens.PearlBlue.copy(alpha = 0.32f),
                            Color.Transparent,
                        ),
                        center = Offset(120f, 120f),
                        radius = 780f,
                    )
                )
        )
        Box(
            modifier = Modifier
                .matchParentSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            WaterTokens.PearlPink.copy(alpha = 0.24f),
                            Color.Transparent,
                        ),
                        center = Offset(900f, 420f),
                        radius = 720f,
                    )
                )
        )
        Box(
            modifier = Modifier
                .matchParentSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            WaterTokens.PearlLavender.copy(alpha = 0.20f),
                            Color.Transparent,
                        ),
                        center = Offset(320f, 1500f),
                        radius = 900f,
                    )
                )
        )
        content()
    }
}

@Composable
fun WaterCareTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = WaterColorScheme,
        typography = WaterTypography,
        shapes = WaterShapes,
        content = content,
    )
}
