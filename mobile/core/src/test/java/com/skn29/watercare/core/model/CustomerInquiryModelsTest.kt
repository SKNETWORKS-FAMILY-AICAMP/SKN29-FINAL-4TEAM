package com.skn29.watercare.core.model

import org.junit.Assert.assertEquals
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
}
