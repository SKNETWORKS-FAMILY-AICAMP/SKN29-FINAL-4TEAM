package com.skn29.watercare.core.model

import com.skn29.watercare.core.network.extractConflict
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Test

class StateConflictMappingTest {
    @Test
    fun conflictPayload_mapsLatestStateVersionAndAllowedActions() {
        val data = Json.parseToJsonElement(
            """
            {
              "current_status": "CONSULTATION_REQUIRED",
              "current_state_version": 4,
              "allowed_actions": ["START_CONSULTATION"]
            }
            """.trimIndent()
        )

        val snapshot = extractConflict(details = null, data = data)
        val action = snapshot?.allowedActions?.single()

        assertNotNull(snapshot)
        assertEquals("CONSULTATION_REQUIRED", snapshot?.currentStatus)
        assertEquals(4, snapshot?.currentStateVersion)
        assertEquals("START_CONSULTATION", action?.code)
        assertEquals("START_CONSULTATION", action?.displayLabel)
        assertFalse(action?.isKnownForIntakeConflict() == true)
    }
}