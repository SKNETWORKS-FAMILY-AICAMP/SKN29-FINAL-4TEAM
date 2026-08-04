package com.skn29.watercare.core.network

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NetworkConflictParserTest {
    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun stringActions_areConvertedToTypedActions() {
        val details = json.parseToJsonElement(
            """
            {
              "current_status": "DRAFT",
              "current_state_version": 2,
              "allowed_actions": [
                "SUBMIT_SYMPTOM",
                "CANCEL_INQUIRY"
              ]
            }
            """.trimIndent()
        ).jsonObject

        val snapshot = extractConflict(details, null)

        assertNotNull(snapshot)
        assertEquals("DRAFT", snapshot?.currentStatus)
        assertEquals(2, snapshot?.currentStateVersion)
        assertEquals(
            listOf("SUBMIT_SYMPTOM", "CANCEL_INQUIRY"),
            snapshot?.allowedActions?.map { it.code },
        )
        assertEquals(
            "최신 상태로 증상 다시 제출",
            snapshot?.allowedActions?.first()?.displayLabel,
        )
        assertTrue(snapshot?.allowedActions?.first()?.isRetrySubmitAction() == true)
    }

    @Test
    fun objectActions_preserveBackendDisplayAndConfirmationMetadata() {
        val details = json.parseToJsonElement(
            """
            {
              "current": {
                "status": "QUESTIONNAIRE_IN_PROGRESS",
                "state_version": 4,
                "allowed_actions": [
                  {
                    "code": "CANCEL_INQUIRY",
                    "label": "문의 취소",
                    "operation_id": "cancelInquiry",
                    "style": "DESTRUCTIVE",
                    "requires_confirmation": true,
                    "confirmation_message": "문의를 취소하시겠습니까?"
                  }
                ]
              }
            }
            """.trimIndent()
        ).jsonObject

        val snapshot = extractConflict(details, null)
        val action = snapshot?.allowedActions?.single()

        assertNotNull(action)
        assertEquals("문의 취소", action?.displayLabel)
        assertEquals("cancelInquiry", action?.operationId)
        assertEquals("DESTRUCTIVE", action?.style)
        assertTrue(action?.requiresConfirmation == true)
        assertEquals("문의를 취소하시겠습니까?", action?.confirmationMessage)
    }

    @Test
    fun unknownAction_isPreservedButNotMarkedAsIntakeSupported() {
        val details = json.parseToJsonElement(
            """
            {
              "current_status": "DRAFT",
              "current_state_version": 1,
              "allowed_actions": ["INTERNAL_ONLY_ACTION", null, 7]
            }
            """.trimIndent()
        ).jsonObject

        val snapshot = extractConflict(details, null)
        val action = snapshot?.allowedActions?.single()

        assertEquals("INTERNAL_ONLY_ACTION", action?.code)
        assertFalse(action?.isKnownForIntakeConflict() == true)
        assertFalse(action?.isRetrySubmitAction() == true)
    }
}
