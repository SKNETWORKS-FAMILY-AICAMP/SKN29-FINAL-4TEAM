package com.skn29.watercare.core.repository

import com.skn29.watercare.core.config.CustomerCareRuntimeConfig
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.ActiveInquirySummary
import com.skn29.watercare.core.model.EvidenceCardData
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.ProductSummary
import com.skn29.watercare.core.model.SymptomIntakeRequest
import java.util.UUID
import kotlinx.coroutines.delay

interface CustomerCareRepository {
    suspend fun getHome(): ApiResult<CustomerHomeData>
    suspend fun submitIntake(request: SymptomIntakeRequest): ApiResult<IntakeSubmission>
    suspend fun getGuidance(inquiryId: String, scenario: MockScenario): ApiResult<GuidanceData>
}

/**
 * Contract-aligned deterministic fixture used until questionnaire/guidance endpoints are routed.
 * It never contains real customer data and is intentionally named Fake.
 */
class FakeCustomerCareRepository(
    private val fixtureSubscriptionId: String =
        CustomerCareRuntimeConfig.DEFAULT_FIXTURE_SUBSCRIPTION_ID,
) : CustomerCareRepository {
    override suspend fun getHome(): ApiResult<CustomerHomeData> {
        delay(180)
        return ApiResult.Success(
            CustomerHomeData(
                subscriptionId = fixtureSubscriptionId,
                product = ProductSummary(
                    productId = "00000000-0000-4000-8000-000000000201",
                    modelCode = "WPUJAC104DWH",
                    modelName = "WPU-JAC104D",
                    serialNo = "SYN-JAC104-002",
                    managementTypeCode = "VISIT_CARE",
                    managementTypeLabel = "방문 관리",
                    isSynthetic = true,
                ),
                questionnaireStatus = "사전 문진 가능",
                nextCareOn = "2026-08-04",
                activeInquiry = ActiveInquirySummary(
                    inquiryId = "00000000-0000-4000-8000-000000000301",
                    inquiryCode = "DEMO-INQ-002",
                    statusCode = "AI_GUIDANCE",
                    statusLabel = "AI 안내 확인",
                ),
            )
        )
    }

    override suspend fun submitIntake(request: SymptomIntakeRequest): ApiResult<IntakeSubmission> {
        delay(350)
        val forced = request.mockScenario?.let { runCatching { MockScenario.valueOf(it) }.getOrNull() }
        val scenario = forced ?: inferScenario(request)
        return when (scenario) {
            MockScenario.NETWORK_FAILURE -> ApiResult.Failure(
                code = "NETWORK_ERROR",
                message = "테스트용 네트워크 연결 실패입니다. 입력값은 유지됩니다.",
                retryable = true,
            )
            MockScenario.AI_FAILURE -> ApiResult.Success(
                IntakeSubmission(
                    inquiryId = UUID.randomUUID().toString(),
                    inquiryCode = "DEMO-AI-FAIL",
                    guidanceScenario = MockScenario.AI_FAILURE.name,
                )
            )
            else -> ApiResult.Success(
                IntakeSubmission(
                    inquiryId = UUID.randomUUID().toString(),
                    inquiryCode = when (scenario) {
                        MockScenario.CAUTION -> "DEMO-CAUTION-001"
                        MockScenario.DANGER -> "DEMO-DANGER-001"
                        MockScenario.NO_EVIDENCE -> "DEMO-NO-EVIDENCE-001"
                        else -> "DEMO-INQ-002"
                    },
                    questionnaireSessionId = UUID.randomUUID().toString(),
                    guidanceScenario = scenario.name,
                )
            )
        }
    }

    override suspend fun getGuidance(inquiryId: String, scenario: MockScenario): ApiResult<GuidanceData> {
        delay(280)
        return when (scenario) {
            MockScenario.NETWORK_FAILURE -> ApiResult.Failure(
                code = "NETWORK_ERROR",
                message = "안내 결과를 불러오지 못했습니다. 네트워크를 확인해 주세요.",
                retryable = true,
            )
            MockScenario.AI_FAILURE -> ApiResult.Failure(
                code = "AI_RESULT_FAILED",
                message = "AI 안내 생성에 실패했습니다. 입력 내용은 저장되어 있으며 상담으로 전환할 수 있습니다.",
                retryable = true,
            )
            MockScenario.CAUTION -> ApiResult.Success(cautionGuidance(inquiryId))
            MockScenario.DANGER -> ApiResult.Success(dangerGuidance(inquiryId))
            MockScenario.NO_EVIDENCE -> ApiResult.Success(noEvidenceGuidance(inquiryId))
            MockScenario.BACKEND_PROCESSING -> ApiResult.Success(backendProcessingGuidance(inquiryId))
            MockScenario.NORMAL -> ApiResult.Success(normalGuidance(inquiryId))
        }
    }

    private fun inferScenario(request: SymptomIntakeRequest): MockScenario {
        val normalized = (request.rawText + " " + request.displayText.orEmpty()).uppercase()
        return when {
            "NETWORK_FAIL" in normalized -> MockScenario.NETWORK_FAILURE
            "AI_FAIL" in normalized -> MockScenario.AI_FAILURE
            "LEAK" in request.symptomCodes || "누수" in request.rawText -> MockScenario.DANGER
            "TEMPERATURE" in request.symptomCodes || "온수" in request.rawText -> MockScenario.CAUTION
            "미지원" in request.rawText || "UNKNOWN" in normalized -> MockScenario.NO_EVIDENCE
            else -> MockScenario.NORMAL
        }
    }

    private fun backendProcessingGuidance(inquiryId: String) = GuidanceData(
        inquiryId = inquiryId,
        inquiryCode = "BACKEND-INQUIRY",
        statusCode = "QUESTIONNAIRE_IN_PROGRESS",
        stateVersion = 2,
        symptomSummary = "문의가 실제 Backend에 접수되었습니다. AI 안내 조회 API는 아직 준비 중입니다.",
        riskLevel = "unknown",
        usageGuidanceStatus = "PENDING_CONSULTATION",
        usageGuidanceMessage = "공식 안내 결과가 준비될 때까지 사용 가능 여부를 임의로 판단하지 않습니다.",
        safeActions = emptyList(),
        escalationConditions = listOf("누수·전기·화상 위험이 있으면 즉시 사용을 중지하고 고객센터에 연락하세요."),
        prohibitedActions = listOf("제품을 분해하거나 오류 의미를 임의로 추정하지 마세요."),
        nextAction = "Backend 처리 상태 확인",
        requiresConsultation = false,
        evidence = emptyList(),
        allowedActions = emptyList(),
    )

    private fun normalGuidance(inquiryId: String) = GuidanceData(
        inquiryId = inquiryId,
        inquiryCode = "DEMO-INQ-002",
        statusCode = "AI_GUIDANCE",
        stateVersion = 3,
        symptomSummary = "출수량이 이전보다 줄었고 필터 교체 이후에도 동일한 증상이 지속됩니다.",
        riskLevel = "general",
        usageGuidanceStatus = "NORMAL",
        usageGuidanceMessage = "현재 즉시 사용 중지가 필요한 위험 징후는 확인되지 않았습니다.",
        safeActions = listOf("출수구 주변의 이물 여부만 육안으로 확인하세요.", "증상이 지속되면 상담을 요청하세요."),
        escalationConditions = listOf("누수·탄 냄새·전원 이상이 함께 발생하면 즉시 사용을 중지하세요."),
        prohibitedActions = listOf("제품을 분해하거나 내부 필터 연결부를 직접 조정하지 마세요."),
        nextAction = "안내 확인 후 증상 지속 여부 기록",
        requiresConsultation = false,
        evidence = listOf(
            EvidenceCardData(
                documentName = "WPU-JAC104D 사용설명서",
                version = "2026-06",
                page = 38,
                structuredSummary = "출수량 저하 시 외부 상태를 확인하고 증상이 계속되면 고객센터 점검을 요청하도록 안내합니다.",
                verificationStatus = "VERIFIED",
                dataClassification = "official",
                officialUrl = null,
            )
        ),
        allowedActions = listOf(AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION, label = "상담 요청")),
    )


    private fun cautionGuidance(inquiryId: String) = GuidanceData(
        inquiryId = inquiryId,
        inquiryCode = "DEMO-CAUTION-001",
        statusCode = "AI_GUIDANCE",
        stateVersion = 3,
        symptomSummary = "온수 온도가 평소와 달라 화상 예방을 위한 일부 기능 제한이 필요합니다.",
        riskLevel = "caution",
        usageGuidanceStatus = "PARTIAL_STOP",
        usageGuidanceMessage = "온수 기능 사용을 잠시 중지하고 냉수·정수만 주의해서 사용하세요.",
        restrictedFunctions = listOf("온수 출수"),
        safeActions = listOf("온수 버튼을 누르지 마세요.", "증상 발생 시점과 표시 문구를 기록하세요."),
        escalationConditions = listOf("과열 냄새·증기·비정상 소리가 있으면 제품 전체 사용을 중지하고 상담을 요청하세요."),
        prohibitedActions = listOf("온도 센서나 내부 배관 직접 점검", "온수를 손으로 반복 확인"),
        nextAction = "온수 사용 중지 후 상담 여부 확인",
        requiresConsultation = false,
        evidence = listOf(
            EvidenceCardData(
                documentName = "WPU-JAC104D 사용설명서",
                version = "2026-06",
                page = 12,
                structuredSummary = "온수 이상이 의심될 때 화상에 주의하고 비정상 상태가 지속되면 점검을 요청하도록 안내합니다.",
                verificationStatus = "VERIFIED",
                dataClassification = "official",
            )
        ),
        allowedActions = listOf(AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION, label = "상담 요청")),
    )

    private fun dangerGuidance(inquiryId: String) = GuidanceData(
        inquiryId = inquiryId,
        inquiryCode = "DEMO-DANGER-001",
        statusCode = "AI_GUIDANCE",
        stateVersion = 3,
        symptomSummary = "제품 하단에서 물이 확인되어 누수 위험 규칙이 우선 적용되었습니다.",
        riskLevel = "danger",
        usageGuidanceStatus = "TOTAL_STOP",
        usageGuidanceMessage = "제품 사용을 즉시 중지하고 젖은 손으로 전원부를 만지지 마세요.",
        restrictedFunctions = listOf("냉수·온수·정수 출수 전체", "제품 전원 조작"),
        safeActions = listOf("제품과 거리를 유지하세요.", "주변에 고인 물로 인한 미끄럼을 주의하세요.", "상담 연결을 요청하세요."),
        escalationConditions = listOf("전기 냄새·연기·스파크가 보이면 제품에 접근하지 말고 긴급 안전 조치를 따르세요."),
        prohibitedActions = listOf("제품 분해", "누수 부위 직접 조임", "젖은 손으로 플러그 접촉"),
        nextAction = "즉시 상담 요청",
        requiresConsultation = true,
        evidence = listOf(
            EvidenceCardData(
                documentName = "WPU-JAC104D 안전 주의사항",
                version = "2026-06",
                page = 5,
                structuredSummary = "누수 또는 전기 위험 징후가 있을 때 사용을 중지하고 임의 분해하지 않도록 안내합니다.",
                verificationStatus = "VERIFIED",
                dataClassification = "official",
            )
        ),
        allowedActions = listOf(AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION, label = "상담 요청")),
    )

    private fun noEvidenceGuidance(inquiryId: String) = GuidanceData(
        inquiryId = inquiryId,
        inquiryCode = "DEMO-NO-EVIDENCE-001",
        statusCode = "AI_GUIDANCE",
        stateVersion = 3,
        symptomSummary = "현재 지원 범위 밖의 표시 문구가 입력되었습니다.",
        riskLevel = "unknown-code",
        usageGuidanceStatus = "UNKNOWN",
        usageGuidanceMessage = "판단 보류",
        safeActions = emptyList(),
        prohibitedActions = listOf("제품을 분해하거나 오류 의미를 추정하지 마세요."),
        escalationConditions = listOf("누수·전기·화상 위험이 있으면 즉시 사용을 중지하세요."),
        nextAction = "상담 확인",
        requiresConsultation = true,
        evidence = emptyList(),
        allowedActions = listOf(AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION, label = "상담 요청")),
    )
}
