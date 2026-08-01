package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CreateInquiryRequest(
    @SerialName("subscription_id") val subscriptionId: String,
    @SerialName("channel_code") val channelCode: String = "MOBILE",
    @SerialName("raw_text") val rawText: String,
    @SerialName("representative_symptom_code") val representativeSymptomCode: String? = null,
    @SerialName("questionnaire_session_id") val questionnaireSessionId: String? = null,
)

@Serializable
data class AllowedAction(
    val code: String,
    val label: String,
    @SerialName("operation_id") val operationId: String,
    val style: String,
    @SerialName("requires_confirmation") val requiresConfirmation: Boolean,
    @SerialName("confirmation_message") val confirmationMessage: String? = null,
)

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
