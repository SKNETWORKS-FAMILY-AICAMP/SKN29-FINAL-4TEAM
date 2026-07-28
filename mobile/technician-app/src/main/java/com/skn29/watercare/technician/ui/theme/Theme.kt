package com.skn29.watercare.technician.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val TechnicianColors = lightColorScheme(
    primary = Color(0xFF1768E5),
    secondary = Color(0xFF00A6A6),
    background = Color(0xFFF5F7FB),
    surface = Color.White
)

@Composable
fun WaterCareTechnicianTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = TechnicianColors,
        content = content
    )
}
