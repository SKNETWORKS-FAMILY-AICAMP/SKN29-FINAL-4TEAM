package com.skn29.watercare.core.network

import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.ApiResult
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.jsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

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

    @Test
    fun guidanceNotReadyDetails_acceptStatusCodeProjection() {
        val details = json.parseToJsonElement(
            """
            {
              "status_code": "AI_GUIDANCE",
              "state_version": 3,
              "allowed_actions": ["REQUEST_CONSULTATION"]
            }
            """.trimIndent()
        ).jsonObject

        val snapshot = extractConflict(details, null)

        assertEquals("AI_GUIDANCE", snapshot?.currentStatus)
        assertEquals(3, snapshot?.currentStateVersion)
        assertEquals(
            "REQUEST_CONSULTATION",
            snapshot?.allowedActions?.single()?.normalizedCode,
        )
    }

    @Test
    fun guidanceNotReadyResponse_isRetryableAndCarriesWorkflowSnapshot() =
        runBlocking {
            val raw =
                """
                {
                  "success": false,
                  "error": {
                    "code": "AI_GUIDANCE_NOT_READY",
                    "message": "AI 안내가 아직 준비되지 않았습니다.",
                    "details": {
                      "inquiry_id": "00000000-0000-4000-8000-000000000301",
                      "status_code": "QUESTIONNAIRE_IN_PROGRESS",
                      "state_version": 2,
                      "allowed_actions": [
                        {"code": "CANCEL_INQUIRY", "label": "문의 취소"}
                      ]
                    }
                  }
                }
                """.trimIndent()
            val result = safeApiCall<JsonElement>(json) {
                Response.error<ApiEnvelope<JsonElement>>(
                    409,
                    raw.toResponseBody("application/json".toMediaType()),
                )
            }

            val failure = result as ApiResult.Failure
            assertEquals("AI_GUIDANCE_NOT_READY", failure.code)
            assertTrue(failure.retryable)
            assertEquals(
                "QUESTIONNAIRE_IN_PROGRESS",
                failure.conflict?.currentStatus,
            )
            assertEquals(2, failure.conflict?.currentStateVersion)
            assertEquals(
                "CANCEL_INQUIRY",
                failure.conflict?.allowedActions?.single()?.normalizedCode,
            )
        }
}
