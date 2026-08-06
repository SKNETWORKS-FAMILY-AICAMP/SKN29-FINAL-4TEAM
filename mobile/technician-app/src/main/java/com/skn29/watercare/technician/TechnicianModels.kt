package com.skn29.watercare.technician

enum class TechnicianVisitRisk(
    val label: String,
) {
    GENERAL("일반"),
    CAUTION("주의"),
    DANGER("위험"),
    UNKNOWN("판단 보류"),
}

data class TechnicianVisitSummary(
    val visitId: String,
    val visitCode: String,
    val customerMaskedName: String,
    val maskedAddress: String,
    val productModel: String,
    val scheduledAt: String,
    val scheduleStatusCode: String,
    val symptomSummary: String,
    val risk: TechnicianVisitRisk,
    val usageRestrictionLabel: String,
    val scenarioId: String,
    val isSynthetic: Boolean = true,
) {
    val scheduleStatusLabel: String
        get() = when (scheduleStatusCode) {
            "ASSIGNING" -> "기사 배정 중"
            "COORDINATING" -> "일정 조율 중"
            "CONFIRMED" -> "방문 확정"
            "IN_PROGRESS" -> "방문 진행 중"
            "WAITING_COMPLETION" -> "완료 대기"
            else -> "상태 확인 필요"
        }
}

data class TechnicianEvidence(
    val documentName: String,
    val revision: String,
    val page: Int,
    val summary: String,
    val verificationStatus: String,
)

data class TechnicianPrecheckReport(
    val visitId: String,
    val visitCode: String,
    val customerMaskedName: String,
    val customerMaskedPhone: String,
    val maskedAddress: String,
    val productModel: String,
    val scheduledAt: String,
    val symptomSummary: String,
    val consultationSummary: String,
    val inspectionCandidates: List<String>,
    val safetyNotice: String,
    val prohibitedActions: List<String>,
    val evidence: List<TechnicianEvidence>,
    val scenarioId: String,
    val isSynthetic: Boolean = true,
)
