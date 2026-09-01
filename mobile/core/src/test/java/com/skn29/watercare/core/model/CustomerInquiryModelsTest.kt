package com.skn29.watercare.core.model

import com.skn29.watercare.core.network.WaterCareApi
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import retrofit2.http.GET
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CustomerInquiryModelsTest {
    @Test
    fun snapshotMapper_preservesBackendRfc3339Value() {
        val dto = CustomerInquirySnapshotDto(
            inquiryId = "00000000-0000-4000-8000-000000000301",
            statusCode = "QUESTIONNAIRE_IN_PROGRESS",
            stateVersion = 2,
            subscriptionId = "00000000-0000-4000-8000-000000000101",
            product = CustomerInquiryProductDto(modelCode = "WPUJAC104DWH"),
            allowedActions = listOf(
                AllowedAction(
                    code = InquiryActionLabels.SUBMIT_ANSWERS,
                    label = "추가 답변 제출",
                )
            ),
            updatedAt = "2026-08-11T15:10:00+09:00",
            consultationReason = "NO_EVIDENCE",
        )
        val mapped = dto.toDomain()
        assertEquals(dto.inquiryId, mapped.inquiryId)
        assertEquals(2, mapped.stateVersion)
        assertEquals("WPUJAC104DWH", mapped.productModelCode)
        assertEquals(
            InquiryActionLabels.SUBMIT_ANSWERS,
            mapped.allowedActions.single().normalizedCode,
        )
        assertEquals("2026-08-11T15:10:00+09:00", mapped.updatedAtRfc3339)
        assertEquals("NO_EVIDENCE", mapped.consultationReason)
    }

    @Test
    fun questionsMapper_keepsPublicQuestionContract() {
        val mapped = CustomerInquiryQuestionsDto(
            inquiryId = "00000000-0000-4000-8000-000000000301",
            stateVersion = 2,
            questions = listOf(
                CustomerInquiryQuestionDto(
                    questionId = "00000000-0000-4000-8000-000000000401",
                    questionType = "SINGLE_CHOICE",
                    prompt = "필터를 최근 교체하셨나요?",
                    required = true,
                    options = listOf(
                        CustomerInquiryQuestionOptionDto("YES", "예"),
                        CustomerInquiryQuestionOptionDto("NO", "아니오"),
                    ),
                )
            ),
        ).toDomain()
        assertEquals(1, mapped.questions.size)
        assertTrue(mapped.questions.single().isSingleChoice)
        assertEquals("YES", mapped.questions.single().options.first().value)
    }

    @Test
    fun answerMapper_emitsExactlyOneSupportedValue() {
        val text = FollowUpAnswer(
            questionId = "question-text",
            answerText = "  이틀 전부터입니다.  ",
        ).toRequestDto()
        assertEquals("이틀 전부터입니다.", text.answerText)
        assertNull(text.answerPayload)

        val choice = FollowUpAnswer(
            questionId = "question-choice",
            selectedOption = " YES ",
        ).toRequestDto()
        assertNull(choice.answerText)
        assertEquals("YES", choice.answerPayload?.selectedOption)
    }
    @Test
    fun activeInquiryEnvelope_decodesServerSnapshotWithoutLosingState() {
        val raw = """
            {
              "success": true,
              "data": {
                "active_inquiry": {
                  "inquiry_id": "00000000-0000-4000-8000-000000000901",
                  "status_code": "COMPLETION_PENDING",
                  "state_version": 10,
                  "subscription_id": "00000000-0000-4000-8000-000000000101",
                  "product": {
                    "model_code": "WPUJAC104DWH"
                  },
                  "allowed_actions": [
                    {
                      "code": "REQUEST_CONSULTATION",
                      "label": "상담 요청",
                      "operation_id": "requestConsultation",
                      "style": "SECONDARY",
                      "requires_confirmation": false,
                      "confirmation_message": null
                    }
                  ],
                  "updated_at": "2026-08-15T10:50:50+09:00"
                }
              },
              "error": null,
              "metadata": {
                "correlation_id": "active-contract-test"
              }
            }
        """.trimIndent()

        val envelope =
            Json.decodeFromString<
                ApiEnvelope<CustomerActiveInquiryDataDto>
            >(raw)

        assertTrue(envelope.success)

        val activeDto =
            requireNotNull(
                requireNotNull(envelope.data).activeInquiry
            )

        val active = activeDto.toDomain()

        assertEquals(
            "00000000-0000-4000-8000-000000000901",
            active.inquiryId,
        )
        assertEquals(
            "COMPLETION_PENDING",
            active.statusCode,
        )
        assertEquals(
            10,
            active.stateVersion,
        )
        assertEquals(
            "00000000-0000-4000-8000-000000000101",
            active.subscriptionId,
        )
        assertEquals(
            "WPUJAC104DWH",
            active.productModelCode,
        )
        assertEquals(
            "REQUEST_CONSULTATION",
            active.allowedActions.single().code,
        )
        assertEquals(
            "requestConsultation",
            active.allowedActions.single().operationId,
        )
        assertEquals(
            "2026-08-15T10:50:50+09:00",
            active.updatedAtRfc3339,
        )
    }

    @Test
    fun activeInquiryEnvelope_decodesNullWithoutSynthesizingInquiry() {
        val raw = """
            {
              "success": true,
              "data": {
                "active_inquiry": null
              },
              "error": null,
              "metadata": {
                "correlation_id": "active-null-test"
              }
            }
        """.trimIndent()

        val envelope =
            Json.decodeFromString<
                ApiEnvelope<CustomerActiveInquiryDataDto>
            >(raw)

        assertTrue(envelope.success)
        assertNull(
            requireNotNull(envelope.data).activeInquiry
        )
    }

    @Test
    fun activeInquiryApi_usesExactBackendGetPath() {
        val methods =
            WaterCareApi::class.java.declaredMethods
                .filter {
                    it.name == "customerActiveInquiry"
                }

        assertEquals(
            1,
            methods.size,
        )

        val get =
            requireNotNull(
                methods.single()
                    .getAnnotation(GET::class.java)
            )

        assertEquals(
            "api/v1/me/inquiries/active",
            get.value,
        )
    }
}
