package com.skn29.watercare.technician.ui.theme

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

private val TechnicianColors = lightColorScheme(
    primary = Color(0xFF1559C5),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE8FF),
    onPrimaryContainer = Color(0xFF0B2D63),
    secondary = Color(0xFF007A72),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFBCEFEA),
    onSecondaryContainer = Color(0xFF00423D),
    tertiary = Color(0xFF5B5F97),
    tertiaryContainer = Color(0xFFE2E1FF),
    onTertiaryContainer = Color(0xFF252858),
    error = Color(0xFFBA1A1A),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    background = Color(0xFFF5F7FB),
    onBackground = Color(0xFF171C24),
    surface = Color.White,
    onSurface = Color(0xFF171C24),
    surfaceVariant = Color(0xFFE8EDF5),
    onSurfaceVariant = Color(0xFF424A57),
    outline = Color(0xFF737C8A)
)

private val TechnicianTypography = Typography(
    titleLarge = TextStyle(
        fontSize = 22.sp,
        lineHeight = 28.sp,
        fontWeight = FontWeight.Bold
    ),
    titleMedium = TextStyle(
        fontSize = 18.sp,
        lineHeight = 24.sp,
        fontWeight = FontWeight.SemiBold
    ),
    bodyLarge = TextStyle(
        fontSize = 16.sp,
        lineHeight = 24.sp
    ),
    bodyMedium = TextStyle(
        fontSize = 14.sp,
        lineHeight = 21.sp
    ),
    labelLarge = TextStyle(
        fontSize = 14.sp,
        lineHeight = 20.sp,
        fontWeight = FontWeight.SemiBold
    )
)

private val TechnicianShapes = Shapes(
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp)
)

@Composable
fun WaterCareTechnicianTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = TechnicianColors,
        typography = TechnicianTypography,
        shapes = TechnicianShapes,
        content = content
    )
}
