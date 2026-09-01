package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CustomerInquiryProductDto(
    @SerialName("model_code") val modelCode: String,
)

@Serializable
data class CustomerActiveInquiryDataDto(
    @SerialName("active_inquiry") val activeInquiry: CustomerInquirySnapshotDto? = null,
)

@Serializable
data class CustomerInquirySnapshotDto(
    @SerialName("inquiry_id") val inquiryId: String,
    @SerialName("status_code") val statusCode: String,
    @SerialName("state_version") val stateVersion: Int,
    @SerialName("subscription_id") val subscriptionId: String,
    val product: CustomerInquiryProductDto,
    @SerialName("allowed_actions") val allowedActions: List<AllowedAction> = emptyList(),
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("consultation_reason") val consultationReason: String? = null,
)

@Serializable
data class CustomerInquiryConsultationResultDto(
    @SerialName("inquiry_id") val inquiryId: String,
    @SerialName("status_code") val statusCode: String,
    @SerialName("state_version") val stateVersion: Int,
    @SerialName("result_code") val resultCode: String,
    @SerialName("result_display_label") val resultDisplayLabel: String,
    @SerialName("customer_guidance") val customerGuidance: String,
    @SerialName("usage_guidance_status") val usageGuidanceStatus: String,
    @SerialName("usage_guidance_display_label")
    val usageGuidanceDisplayLabel: String,
    @SerialName("completed_at") val completedAt: String,
    @SerialName("allowed_actions")
    val allowedActions: List<AllowedAction> = emptyList(),
)

@Serializable
data class CustomerInquiryQuestionOptionDto(
    val value: String,
    val label: String,
)

@Serializable
data class CustomerInquiryQuestionDto(
    @SerialName("question_id") val questionId: String,
    @SerialName("question_type") val questionType: String,
    val prompt: String,
    val required: Boolean,
    val options: List<CustomerInquiryQuestionOptionDto> = emptyList(),
)

@Serializable
data class CustomerInquiryQuestionsDto(
    @SerialName("inquiry_id") val inquiryId: String,
    @SerialName("state_version") val stateVersion: Int,
    val questions: List<CustomerInquiryQuestionDto> = emptyList(),
)

@Serializable
data class FollowUpAnswerPayloadDto(
    @SerialName("selected_option") val selectedOption: String,
)

@Serializable
data class FollowUpAnswerItemDto(
    @SerialName("question_id") val questionId: String,
    @SerialName("answer_text") val answerText: String? = null,
    @SerialName("answer_payload") val answerPayload: FollowUpAnswerPayloadDto? = null,
)

@Serializable
data class SubmitFollowUpAnswersRequestDto(
    @SerialName("state_version") val stateVersion: Int,
    val answers: List<FollowUpAnswerItemDto>,
)

@Serializable
data class SubmitFollowUpAnswersResponseDto(
    val message: String,
    @SerialName("inquiry_id") val inquiryId: String,
    val status: String,
    @SerialName("state_version") val stateVersion: Int,
    @SerialName("allowed_actions") val allowedActions: List<AllowedAction> = emptyList(),
    @SerialName("idempotent_replay") val idempotentReplay: Boolean,
    val resource: kotlinx.serialization.json.JsonElement? = null,
)

@Serializable
data class RequestConsultationRequestDto(
    @SerialName("state_version") val stateVersion: Int,
)

@Serializable
data class RequestConsultationResponseDto(
    val message: String,
    @SerialName("inquiry_id") val inquiryId: String,
    val status: String,
    @SerialName("state_version") val stateVersion: Int,
    @SerialName("allowed_actions") val allowedActions: List<AllowedAction> = emptyList(),
    @SerialName("idempotent_replay") val idempotentReplay: Boolean,
    val resource: kotlinx.serialization.json.JsonElement? = null,
)

data class RequestConsultationResult(
    val message: String,
    val inquiryId: String,
    val statusCode: String,
    val stateVersion: Int,
    val allowedActions: List<AllowedAction>,
    val idempotentReplay: Boolean,
)
data class CustomerInquirySnapshot(
    val inquiryId: String,
    val statusCode: String,
    val stateVersion: Int,
    val subscriptionId: String,
    val productModelCode: String,
    val allowedActions: List<AllowedAction>,
    /** RFC3339 원문. Z / +09:00 표현 모양 자체를 비교하지 않는다. */
    val updatedAtRfc3339: String,
    val consultationReason: String? = null,
)

data class CustomerInquiryConsultationResult(
    val inquiryId: String,
    val statusCode: String,
    val stateVersion: Int,
    val resultCode: String,
    val resultDisplayLabel: String,
    val customerGuidance: String,
    val usageGuidanceStatus: String,
    val usageGuidanceDisplayLabel: String,
    val completedAt: String,
    val allowedActions: List<AllowedAction>,
)

data class CustomerInquiryQuestionOption(
    val value: String,
    val label: String,
)

data class CustomerInquiryQuestion(
    val questionId: String,
    val questionType: String,
    val prompt: String,
    val required: Boolean,
    val options: List<CustomerInquiryQuestionOption>,
) {
    val isFreeText: Boolean
        get() = questionType == FREE_TEXT

    val isSingleChoice: Boolean
        get() = questionType == SINGLE_CHOICE

    companion object {
        const val FREE_TEXT = "FREE_TEXT"
        const val SINGLE_CHOICE = "SINGLE_CHOICE"
    }
}

data class CustomerInquiryQuestions(
    val inquiryId: String,
    val stateVersion: Int,
    val questions: List<CustomerInquiryQuestion>,
)

data class FollowUpAnswer(
    val questionId: String,
    val answerText: String? = null,
    val selectedOption: String? = null,
) {
    fun normalized(): FollowUpAnswer = copy(
        questionId = questionId.trim(),
        answerText = answerText?.trim(),
        selectedOption = selectedOption?.trim(),
    )

    val isValid: Boolean
        get() {
            val value = normalized()
            val hasText = !value.answerText.isNullOrBlank()
            val hasOption = !value.selectedOption.isNullOrBlank()
            return value.questionId.isNotBlank() && hasText.xor(hasOption)
        }
}

data class SubmitFollowUpAnswersResult(
    val message: String,
    val inquiryId: String,
    val statusCode: String,
    val stateVersion: Int,
    val allowedActions: List<AllowedAction>,
    val idempotentReplay: Boolean,
)

fun CustomerInquirySnapshotDto.toDomain(): CustomerInquirySnapshot =
    CustomerInquirySnapshot(
        inquiryId = inquiryId,
        statusCode = statusCode,
        stateVersion = stateVersion,
        subscriptionId = subscriptionId,
        productModelCode = product.modelCode,
        allowedActions = allowedActions,
        updatedAtRfc3339 = updatedAt,
        consultationReason = consultationReason,
    )

fun CustomerInquiryConsultationResultDto.toDomain():
    CustomerInquiryConsultationResult =
    CustomerInquiryConsultationResult(
        inquiryId = inquiryId,
        statusCode = statusCode,
        stateVersion = stateVersion,
        resultCode = resultCode,
        resultDisplayLabel = resultDisplayLabel,
        customerGuidance = customerGuidance,
        usageGuidanceStatus = usageGuidanceStatus,
        usageGuidanceDisplayLabel = usageGuidanceDisplayLabel,
        completedAt = completedAt,
        allowedActions = allowedActions,
    )

fun CustomerInquiryQuestionsDto.toDomain(): CustomerInquiryQuestions =
    CustomerInquiryQuestions(
        inquiryId = inquiryId,
        stateVersion = stateVersion,
        questions = questions.map { question ->
            CustomerInquiryQuestion(
                questionId = question.questionId,
                questionType = question.questionType,
                prompt = question.prompt,
                required = question.required,
                options = question.options.map { option ->
                    CustomerInquiryQuestionOption(
                        value = option.value,
                        label = option.label,
                    )
                },
            )
        },
    )

fun FollowUpAnswer.toRequestDto(): FollowUpAnswerItemDto {
    val value = normalized()
    require(value.isValid) {
        "Follow-up answer must contain exactly one supported answer value."
    }
    return if (!value.answerText.isNullOrBlank()) {
        FollowUpAnswerItemDto(
            questionId = value.questionId,
            answerText = value.answerText,
        )
    } else {
        FollowUpAnswerItemDto(
            questionId = value.questionId,
            answerPayload = FollowUpAnswerPayloadDto(
                selectedOption = requireNotNull(value.selectedOption),
            ),
        )
    }
}

fun SubmitFollowUpAnswersResponseDto.toDomain(): SubmitFollowUpAnswersResult =
    SubmitFollowUpAnswersResult(
        message = message,
        inquiryId = inquiryId,
        statusCode = status,
        stateVersion = stateVersion,
        allowedActions = allowedActions,
        idempotentReplay = idempotentReplay,
    )
fun RequestConsultationResponseDto.toDomain(): RequestConsultationResult =
    RequestConsultationResult(
        message = message,
        inquiryId = inquiryId,
        statusCode = status,
        stateVersion = stateVersion,
        allowedActions = allowedActions,
        idempotentReplay = idempotentReplay,
    )
