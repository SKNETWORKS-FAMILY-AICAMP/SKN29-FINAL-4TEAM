package com.skn29.watercare.core.model

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertTrue
import org.junit.Test

class ResolutionModelsSerializationTest {
    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        isLenient = false
    }

    @Test
    fun resolutionFeedback_alwaysSerializesResolvedTrue() {
        val encoded = json.encodeToString(
            ResolutionFeedbackRequestDto(
                stateVersion = 9,
                resolved = true,
            )
        )

        assertTrue(encoded.contains("\"resolved\":true"))
    }

    @Test
    fun reportUnresolved_alwaysSerializesResolvedFalse() {
        val encoded = json.encodeToString(
            ReportUnresolvedRequestDto(
                stateVersion = 9,
                resolved = false,
                reasonCode = "STILL_UNRESOLVED",
            )
        )

        assertTrue(encoded.contains("\"resolved\":false"))
    }
}
