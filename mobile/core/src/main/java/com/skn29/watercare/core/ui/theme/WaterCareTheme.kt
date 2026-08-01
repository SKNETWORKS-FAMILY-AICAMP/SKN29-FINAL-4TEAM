package com.skn29.watercare.core.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

val WaterSky = Color(0xFF3DB7FF)
val WaterSkyDark = Color(0xFF126BB5)
val WaterAqua = Color(0xFF7EE6E6)
val WaterSkySoft = Color(0xFFEAF8FF)

val WaterOrange = Color(0xFFFF9D3A)
val WaterOrangeDark = Color(0xFFF47D18)
val WaterOrangeSoft = Color(0xFFFFEAD1)

val WaterBackground = Color(0xFFF7FBFF)
val WaterCard = Color(0xFFFFFFFF)
val WaterText = Color(0xFF153653)
val WaterSubText = Color(0xFF668298)
val WaterBorder = Color(0xFFD7EAF6)
val WaterSuccess = Color(0xFF20A66A)
val WaterDanger = Color(0xFFE55252)

private val WaterColorScheme = lightColorScheme(
    primary = WaterSkyDark,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDFF4FF),
    onPrimaryContainer = WaterText,
    secondary = WaterAqua,
    onSecondary = WaterText,
    secondaryContainer = WaterSkySoft,
    onSecondaryContainer = WaterText,
    tertiary = WaterOrange,
    onTertiary = Color.White,
    tertiaryContainer = WaterOrangeSoft,
    onTertiaryContainer = Color(0xFF6D3900),
    background = WaterBackground,
    onBackground = WaterText,
    surface = WaterCard,
    onSurface = WaterText,
    surfaceVariant = Color(0xFFF2F8FC),
    onSurfaceVariant = WaterSubText,
    outline = WaterBorder,
    error = WaterDanger,
    onError = Color.White,
    errorContainer = Color(0xFFFFE3E3),
    onErrorContainer = Color(0xFF671B1B),
)

private val WaterShapes = Shapes(
    extraSmall = RoundedCornerShape(10.dp),
    small = RoundedCornerShape(14.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(28.dp),
    extraLarge = RoundedCornerShape(34.dp),
)

@Composable
fun WaterCareTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = WaterColorScheme,
        typography = Typography(),
        shapes = WaterShapes,
        content = content,
    )
}
