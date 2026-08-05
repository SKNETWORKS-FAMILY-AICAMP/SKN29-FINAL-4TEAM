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
    fun liquidGlassRenderedAlphaAndRadiusMatchSharedSpecification() {
        /*
         * Compose Color is converted to 8-bit ARGB at render boundaries.
         * Verify the rendered alpha byte instead of comparing floating-point
         * alpha values with an unrealistically narrow tolerance.
         */
        assertEquals(
            0x8CFFFFFF.toInt(),
            WaterTokens.GlassFill.toArgb(),
        )
        assertEquals(
            0xB8FFFFFF.toInt(),
            WaterTokens.GlassFillStrong.toArgb(),
        )
        assertEquals(
            0xA6FFFFFF.toInt(),
            WaterTokens.GlassBorder.toArgb(),
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
