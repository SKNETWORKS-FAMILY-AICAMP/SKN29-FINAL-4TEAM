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

/** Backend canonical inquiry status values. The raw DTO remains a String. */
enum class KnownInquiryStatus {
    DRAFT,
    QUESTIONNAIRE_IN_PROGRESS,
    AI_GUIDANCE,
    CONSULTATION_REQUIRED,
    CONSULTATION_IN_PROGRESS,
    VISIT_REVIEW_PENDING,
    VISIT_SCHEDULING,
    VISIT_SCHEDULED,
    COMPLETION_PENDING,
    REVISIT_REQUIRED,
    REOPENED,
    RESOLVED,
    CANCELLED,
}

data class ServerInquiryStatus(
    val rawCode: String,
    val known: KnownInquiryStatus?,
) {
    companion object {
        fun parse(rawCode: String): ServerInquiryStatus {
            val normalized = rawCode.trim().uppercase()
            return ServerInquiryStatus(
                rawCode = rawCode,
                known = KnownInquiryStatus.entries.firstOrNull { it.name == normalized },
            )
        }
    }
}

/** UI grouping only. It is never sent to Backend as a workflow event or status. */
enum class InquiryDisplayState {
    DRAFT,
    QUESTIONNAIRE,
    GUIDANCE,
    CONSULTATION,
    VISIT,
    COMPLETION,
    RESOLVED,
    CANCELLED,
    UNKNOWN,
}

/** Backend canonical visit values kept separate from location/tracking display states. */
enum class KnownVisitStatus {
    ASSIGNING,
    SCHEDULING,
    CONFIRMED,
    IN_PROGRESS,
    COMPLETED,
    FOLLOW_UP_REQUIRED,
    CANCELLED,
}

data class ServerVisitStatus(
    val rawCode: String,
    val known: KnownVisitStatus?,
) {
    companion object {
        fun parse(rawCode: String): ServerVisitStatus {
            val normalized = rawCode.trim().uppercase()
            return ServerVisitStatus(
                rawCode = rawCode,
                known = KnownVisitStatus.entries.firstOrNull { it.name == normalized },
            )
        }
    }
}

enum class VisitDisplayState {
    WAITING,
    CONFIRMED,
    WORKING,
    COMPLETED,
    FOLLOW_UP,
    CANCELLED,
    UNKNOWN,
}

data class RuntimeAllowedAction(
    val code: String,
    val label: String?,
    val operationId: String?,
    val style: String?,
    val requiresConfirmation: Boolean,
    val confirmationMessage: String?,
    val objectContractAvailable: Boolean,
)

fun AllowedAction.toRuntimeAction(): RuntimeAllowedAction = RuntimeAllowedAction(
    code = code,
    label = label,
    operationId = operationId,
    style = style,
    requiresConfirmation = requiresConfirmation,
    confirmationMessage = confirmationMessage,
    objectContractAvailable = true,
)

fun String.toCodeOnlyRuntimeAction(): RuntimeAllowedAction = RuntimeAllowedAction(
    code = this,
    label = null,
    operationId = null,
    style = null,
    requiresConfirmation = false,
    confirmationMessage = null,
    objectContractAvailable = false,
)

data class InquiryRuntimeSnapshot(
    val inquiryId: String,
    val inquiryCode: String,
    val serverStatus: ServerInquiryStatus,
    val displayState: InquiryDisplayState,
    val stateVersion: Int,
    val allowedActions: List<RuntimeAllowedAction>,
    val correlationId: String?,
    val idempotentReplay: Boolean,
)

object InquiryStatusMapper {
    fun displayState(status: ServerInquiryStatus): InquiryDisplayState = when (status.known) {
        KnownInquiryStatus.DRAFT -> InquiryDisplayState.DRAFT
        KnownInquiryStatus.QUESTIONNAIRE_IN_PROGRESS -> InquiryDisplayState.QUESTIONNAIRE
        KnownInquiryStatus.AI_GUIDANCE -> InquiryDisplayState.GUIDANCE
        KnownInquiryStatus.CONSULTATION_REQUIRED,
        KnownInquiryStatus.CONSULTATION_IN_PROGRESS -> InquiryDisplayState.CONSULTATION
        KnownInquiryStatus.VISIT_REVIEW_PENDING,
        KnownInquiryStatus.VISIT_SCHEDULING,
        KnownInquiryStatus.VISIT_SCHEDULED,
        KnownInquiryStatus.REVISIT_REQUIRED -> InquiryDisplayState.VISIT
        KnownInquiryStatus.COMPLETION_PENDING,
        KnownInquiryStatus.REOPENED -> InquiryDisplayState.COMPLETION
        KnownInquiryStatus.RESOLVED -> InquiryDisplayState.RESOLVED
        KnownInquiryStatus.CANCELLED -> InquiryDisplayState.CANCELLED
        null -> InquiryDisplayState.UNKNOWN
    }

    fun label(status: ServerInquiryStatus): String = when (status.known) {
        KnownInquiryStatus.DRAFT -> "작성 중"
        KnownInquiryStatus.QUESTIONNAIRE_IN_PROGRESS -> "문진 진행 중"
        KnownInquiryStatus.AI_GUIDANCE -> "AI 안내"
        KnownInquiryStatus.CONSULTATION_REQUIRED -> "상담 필요"
        KnownInquiryStatus.CONSULTATION_IN_PROGRESS -> "상담 진행 중"
        KnownInquiryStatus.VISIT_REVIEW_PENDING -> "방문 검토 중"
        KnownInquiryStatus.VISIT_SCHEDULING -> "일정 조율 중"
        KnownInquiryStatus.VISIT_SCHEDULED -> "방문 확정"
        KnownInquiryStatus.COMPLETION_PENDING -> "완료 확인 대기"
        KnownInquiryStatus.REVISIT_REQUIRED -> "재방문 필요"
        KnownInquiryStatus.REOPENED -> "문의 재개"
        KnownInquiryStatus.RESOLVED -> "해결 완료"
        KnownInquiryStatus.CANCELLED -> "취소됨"
        null -> "확인 중 (${status.rawCode})"
    }
}

object InquiryLabels {
    fun status(code: String): String = InquiryStatusMapper.label(ServerInquiryStatus.parse(code))

    fun action(code: String): String = when (code) {
        "SUBMIT_SYMPTOM" -> "증상 제출"
        "CANCEL_INQUIRY" -> "문의 취소"
        "REQUEST_CONSULTATION" -> "상담 요청"
        else -> code
    }
}
