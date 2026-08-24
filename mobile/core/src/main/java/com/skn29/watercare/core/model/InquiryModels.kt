package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CreateInquiryRequest(
    @SerialName("subscription_id") val subscriptionId: String,
    @SerialName("channel_code") val channelCode: String,
    @SerialName("raw_text") val rawText: String,
    @SerialName("representative_symptom_code") val representativeSymptomCode: String? = null,
    @SerialName("questionnaire_session_id") val questionnaireSessionId: String? = null,
)

@Serializable
data class AllowedAction(
    val code: String,
    val label: String = "",
    @SerialName("operation_id") val operationId: String = "",
    val style: String = "UNKNOWN",
    @SerialName("requires_confirmation") val requiresConfirmation: Boolean = false,
    @SerialName("confirmation_message") val confirmationMessage: String? = null,
) {
    val normalizedCode: String
        get() = code.trim().uppercase()

    val displayLabel: String
        get() = label.trim().takeIf(String::isNotEmpty)
            ?: InquiryActionLabels.label(normalizedCode)

    fun isKnownForIntakeConflict(): Boolean =
        normalizedCode in InquiryActionLabels.intakeConflictCodes

    fun isRetrySubmitAction(): Boolean =
        normalizedCode == InquiryActionLabels.SUBMIT_SYMPTOM
}

object InquiryActionLabels {
    const val SUBMIT_SYMPTOM = "SUBMIT_SYMPTOM"
    const val SUBMIT_ANSWERS = "SUBMIT_ANSWERS"
    const val CANCEL_INQUIRY = "CANCEL_INQUIRY"
    const val REQUEST_CONSULTATION = "REQUEST_CONSULTATION"
    const val SUBMIT_RESOLUTION_FEEDBACK = "SUBMIT_RESOLUTION_FEEDBACK"
    const val CUSTOMER_REPORTED_UNRESOLVED = "CUSTOMER_REPORTED_UNRESOLVED"

    val intakeConflictCodes: Set<String> = setOf(
        SUBMIT_SYMPTOM,
        SUBMIT_ANSWERS,
        CANCEL_INQUIRY,
        REQUEST_CONSULTATION,
    )

    fun label(code: String): String = when (code.trim().uppercase()) {
        SUBMIT_SYMPTOM -> "최신 상태로 증상 다시 제출"
        SUBMIT_ANSWERS -> "추가 답변 제출"
        CANCEL_INQUIRY -> "문의 취소"
        REQUEST_CONSULTATION -> "상담 요청"
        SUBMIT_RESOLUTION_FEEDBACK -> "해결됐어요"
        CUSTOMER_REPORTED_UNRESOLVED -> "아직 해결되지 않았어요"
        else -> code.trim()
    }
}

@Serializable
data class InquiryResponse(
    @SerialName("inquiry_id") val inquiryId: String,
    @SerialName("inquiry_code") val inquiryCode: String,
    @SerialName("status_code") val statusCode: String,
    @SerialName("state_version") val stateVersion: Int,
    @SerialName("idempotent_replay") val idempotentReplay: Boolean,
    @SerialName("allowed_actions") val allowedActions: List<AllowedAction> = emptyList(),
)

@Serializable
data class SubmitSymptomRequest(
    @SerialName("state_version") val stateVersion: Int,
)

@Serializable
data class SubmitSymptomResponse(
    @SerialName("inquiry_id") val inquiryId: String,
    val state: String,
    @SerialName("state_version") val stateVersion: Int,
    @SerialName("idempotent_replay") val idempotentReplay: Boolean,
    @SerialName("allowed_actions") val allowedActions: List<AllowedAction> = emptyList(),
)

@Serializable
data class CancelInquiryRequest(
    @SerialName("state_version") val stateVersion: Int,
    @SerialName("reason_code") val reasonCode: String,
    @SerialName("reason_detail") val reasonDetail: String? = null,
)

@Serializable
data class CancelInquiryResponse(
    @SerialName("inquiry_id") val inquiryId: String,
    val state: String,
    @SerialName("state_version") val stateVersion: Int,
    @SerialName("idempotent_replay") val idempotentReplay: Boolean,
)

object InquiryLabels {
    fun status(code: String): String = when (code) {
        "DRAFT" -> "작성 중"
        "QUESTIONNAIRE_IN_PROGRESS" -> "문진 진행 중"
        "AI_GUIDANCE" -> "AI 안내"
        "CONSULTATION_REQUIRED" -> "상담 필요"
        "CONSULTATION_IN_PROGRESS" -> "상담 진행 중"
        "VISIT_REVIEW_PENDING" -> "방문 검토 중"
        "VISIT_SCHEDULING" -> "일정 조율 중"
        "VISIT_SCHEDULED" -> "방문 확정"
        "COMPLETION_PENDING" -> "완료 확인 대기"
        "REVISIT_REQUIRED" -> "재방문 필요"
        "REOPENED" -> "문의 재개"
        "RESOLVED" -> "해결 완료"
        "CANCELLED" -> "취소됨"
        else -> "확인 중 ($code)"
    }
}
