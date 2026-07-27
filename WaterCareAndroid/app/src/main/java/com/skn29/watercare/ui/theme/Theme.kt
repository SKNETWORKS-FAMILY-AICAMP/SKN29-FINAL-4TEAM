package com.skn29.watercare.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val WaterCareLightColors = lightColorScheme(
    primary = Color(0xFF1768E5),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE3EEFF),
    onPrimaryContainer = Color(0xFF0C326B),
    secondary = Color(0xFF00A6A6),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD9F7F5),
    onSecondaryContainer = Color(0xFF003B3B),
    tertiary = Color(0xFF6757C8),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFE9E5FF),
    onTertiaryContainer = Color(0xFF261A70),
    background = Color(0xFFF5F7FB),
    onBackground = Color(0xFF172033),
    surface = Color.White,
    onSurface = Color(0xFF172033),
    surfaceVariant = Color(0xFFEDF2F8),
    onSurfaceVariant = Color(0xFF566174),
    outline = Color(0xFFD6DEE9),
    outlineVariant = Color(0xFFE7ECF3),
    error = Color(0xFFD33B3B),
    onError = Color.White,
    errorContainer = Color(0xFFFFE8E8),
    onErrorContainer = Color(0xFF721414)
)

private val WaterCareTypography = Typography(
    headlineMedium = TextStyle(
        fontSize = 28.sp,
        lineHeight = 36.sp,
        fontWeight = FontWeight.ExtraBold,
        letterSpacing = (-0.4).sp
    ),
    headlineSmall = TextStyle(
        fontSize = 23.sp,
        lineHeight = 30.sp,
        fontWeight = FontWeight.ExtraBold,
        letterSpacing = (-0.25).sp
    ),
    titleLarge = TextStyle(
        fontSize = 20.sp,
        lineHeight = 27.sp,
        fontWeight = FontWeight.Bold
    ),
    titleMedium = TextStyle(
        fontSize = 17.sp,
        lineHeight = 24.sp,
        fontWeight = FontWeight.Bold
    ),
    bodyLarge = TextStyle(
        fontSize = 16.sp,
        lineHeight = 24.sp,
        fontWeight = FontWeight.Normal
    ),
    bodyMedium = TextStyle(
        fontSize = 14.sp,
        lineHeight = 21.sp,
        fontWeight = FontWeight.Normal
    ),
    labelLarge = TextStyle(
        fontSize = 15.sp,
        lineHeight = 20.sp,
        fontWeight = FontWeight.Bold
    )
)

private val WaterCareShapes = Shapes(
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(30.dp)
)

@Composable
fun WaterCareTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = WaterCareLightColors,
        typography = WaterCareTypography,
        shapes = WaterCareShapes,
        content = content
    )
}
