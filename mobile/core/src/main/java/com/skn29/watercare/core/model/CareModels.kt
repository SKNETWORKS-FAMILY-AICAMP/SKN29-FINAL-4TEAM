package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Mobile-safe domain values. UNKNOWN is never sent as a normal server value. */
enum class RiskLevel { GENERAL, CAUTION, DANGER, UNKNOWN }
enum class UsageGuidanceStatus { NORMAL, PARTIAL_STOP, TOTAL_STOP, PENDING_CONSULTATION, UNKNOWN }
enum class DataClassification { OFFICIAL, TEAM_DESIGNED, SYNTHETIC, UNKNOWN }
enum class EntryMode { CARE_PRECHECK, ADHOC_INQUIRY }
enum class MockScenario { NORMAL, CAUTION, DANGER, NO_EVIDENCE, AI_FAILURE, NETWORK_FAILURE }

enum class SymptomTopic(val code: String, val label: String) {
    LOW_FLOW("LOW_FLOW", "출수량 저하"),
    TASTE_ODOR("TASTE_ODOR", "물맛·냄새 이상"),
    LEAK("LEAK", "제품 누수"),
    TEMPERATURE("TEMPERATURE", "냉·온수 온도 이상"),
    OTHER("OTHER", "기타 증상"),
}

@Serializable
data class ProductSummary(
    @SerialName("product_id") val productId: String,
    @SerialName("model_code") val modelCode: String,
    @SerialName("model_name") val modelName: String,
    @SerialName("serial_no") val serialNo: String,
    @SerialName("management_type_code") val managementTypeCode: String,
    @SerialName("management_type_label") val managementTypeLabel: String,
    @SerialName("is_synthetic") val isSynthetic: Boolean,
)

@Serializable
data class ActiveInquirySummary(
    @SerialName("inquiry_id") val inquiryId: String,
    @SerialName("inquiry_code") val inquiryCode: String,
    @SerialName("status_code") val statusCode: String,
    @SerialName("status_label") val statusLabel: String,
)

@Serializable
data class CustomerHomeData(
    @SerialName("subscription_id") val subscriptionId: String,
    val product: ProductSummary,
    @SerialName("questionnaire_status") val questionnaireStatus: String,
    @SerialName("next_care_on") val nextCareOn: String,
    @SerialName("active_inquiry") val activeInquiry: ActiveInquirySummary? = null,
)

data class IntakeSubmission(
    val inquiryId: String,
    val inquiryCode: String,
    val statusCode: String,
    val stateVersion: Int,
    val allowedActionCodes: List<String>,
    val correlationId: String?,
    val idempotentReplay: Boolean,
    val guidanceScenario: String,
)

@Serializable
data class EvidenceCardData(
    @SerialName("document_name") val documentName: String,
    val version: String,
    val page: Int? = null,
    @SerialName("structured_summary") val structuredSummary: String,
    @SerialName("verification_status") val verificationStatus: String,
    @SerialName("data_classification") val dataClassification: String,
    @SerialName("official_url") val officialUrl: String? = null,
)

@Serializable
data class GuidanceData(
    @SerialName("inquiry_id") val inquiryId: String,
    @SerialName("inquiry_code") val inquiryCode: String,
    @SerialName("symptom_summary") val symptomSummary: String,
    @SerialName("risk_level") val riskLevel: String,
    @SerialName("usage_guidance_status") val usageGuidanceStatus: String,
    @SerialName("usage_guidance_message") val usageGuidanceMessage: String,
    @SerialName("restricted_functions") val restrictedFunctions: List<String> = emptyList(),
    @SerialName("safe_actions") val safeActions: List<String> = emptyList(),
    @SerialName("escalation_conditions") val escalationConditions: List<String> = emptyList(),
    @SerialName("prohibited_actions") val prohibitedActions: List<String> = emptyList(),
    @SerialName("next_action") val nextAction: String,
    @SerialName("requires_consultation") val requiresConsultation: Boolean,
    val evidence: List<EvidenceCardData> = emptyList(),
    @SerialName("allowed_actions") val allowedActions: List<String> = emptyList(),
)

data class GuidanceDisplayModel(
    val inquiryId: String,
    val inquiryCode: String,
    val symptomSummary: String,
    val riskLevel: RiskLevel,
    val usageStatus: UsageGuidanceStatus,
    val usageMessage: String,
    val restrictedFunctions: List<String>,
    val safeActions: List<String>,
    val escalationConditions: List<String>,
    val prohibitedActions: List<String>,
    val nextAction: String,
    val requiresConsultation: Boolean,
    val evidence: List<EvidenceCardData>,
    val allowedActions: List<String>,
)

object GuidanceMapper {
    fun map(source: GuidanceData): GuidanceDisplayModel {
        val risk = parseRiskLevel(source.riskLevel)
        val usage = parseUsageGuidanceStatus(source.usageGuidanceStatus)
        val unknownCode = risk == RiskLevel.UNKNOWN || usage == UsageGuidanceStatus.UNKNOWN
        val noEvidence = source.evidence.isEmpty()
        val mustConsult = source.requiresConsultation || unknownCode || noEvidence
        val safeUsage = if (unknownCode || noEvidence) UsageGuidanceStatus.PENDING_CONSULTATION else usage
        return GuidanceDisplayModel(
            inquiryId = source.inquiryId,
            inquiryCode = source.inquiryCode,
            symptomSummary = source.symptomSummary,
            riskLevel = if (unknownCode) RiskLevel.UNKNOWN else risk,
            usageStatus = safeUsage,
            usageMessage = if (unknownCode || noEvidence) {
                "공식 근거를 확인하지 못해 사용 가능 여부를 판단하지 않습니다. 상담 확인이 필요합니다."
            } else source.usageGuidanceMessage,
            restrictedFunctions = if (unknownCode || noEvidence) emptyList() else source.restrictedFunctions,
            safeActions = if (unknownCode || noEvidence) emptyList() else source.safeActions,
            escalationConditions = source.escalationConditions,
            prohibitedActions = source.prohibitedActions,
            nextAction = if (mustConsult) "상담 요청" else source.nextAction,
            requiresConsultation = mustConsult,
            evidence = source.evidence,
            allowedActions = source.allowedActions,
        )
    }

    fun parseRiskLevel(value: String): RiskLevel = when (value.trim().lowercase()) {
        "general" -> RiskLevel.GENERAL
        "caution" -> RiskLevel.CAUTION
        "danger" -> RiskLevel.DANGER
        else -> RiskLevel.UNKNOWN
    }

    fun parseUsageGuidanceStatus(value: String): UsageGuidanceStatus = when (value.trim().uppercase()) {
        "NORMAL" -> UsageGuidanceStatus.NORMAL
        "PARTIAL_STOP" -> UsageGuidanceStatus.PARTIAL_STOP
        "TOTAL_STOP" -> UsageGuidanceStatus.TOTAL_STOP
        "PENDING_CONSULTATION" -> UsageGuidanceStatus.PENDING_CONSULTATION
        else -> UsageGuidanceStatus.UNKNOWN
    }

}
