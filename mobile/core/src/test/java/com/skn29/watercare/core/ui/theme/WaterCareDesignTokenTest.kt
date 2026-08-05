package com.skn29.watercare.core.ui.theme

import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Test

class WaterCareDesignTokenTest {
    @Test
    fun liquidGlassColorsMatchSharedSpecification() {
        assertEquals(
            0xFFF2F9FB.toInt(),
            WaterTokens.Water50.toArgb(),
        )
        assertEquals(
            0xFFDCEEF3.toInt(),
            WaterTokens.Water100.toArgb(),
        )
        assertEquals(
            0xFF2E8BA3.toInt(),
            WaterTokens.Water500.toArgb(),
        )
        assertEquals(
            0xFF1B5A6B.toInt(),
            WaterTokens.Water700.toArgb(),
        )
        assertEquals(
            0xFF12262B.toInt(),
            WaterTokens.Ink900.toArgb(),
        )
        assertEquals(
            0xFFC08A2E.toInt(),
            WaterTokens.Caution.toArgb(),
        )
        assertEquals(
            0xFFC0392B.toInt(),
            WaterTokens.Danger.toArgb(),
        )
    }

    @Test
    fun liquidGlassAlphaAndRadiusMatchSharedSpecification() {
        assertEquals(
            0.55f,
            WaterTokens.GlassFill.alpha,
            0.001f,
        )
        assertEquals(
            0.72f,
            WaterTokens.GlassFillStrong.alpha,
            0.001f,
        )
        assertEquals(
            0.65f,
            WaterTokens.GlassBorder.alpha,
            0.001f,
        )
        assertEquals(
            24.dp,
            WaterTokens.RadiusCard,
        )
        assertEquals(
            16.dp,
            WaterTokens.RadiusControl,
        )
    }
}
