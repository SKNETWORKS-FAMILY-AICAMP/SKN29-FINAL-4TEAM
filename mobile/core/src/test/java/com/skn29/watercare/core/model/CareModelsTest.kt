package com.skn29.watercare.core.model

import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CareModelsTest {
    @Test
    fun customerGuidanceDto_decodesAllRequiredBackendFields() {
        val dto = Json.decodeFromString<CustomerInquiryGuidanceDto>(
            """
            {
              "inquiry_id":"00000000-0000-4000-8000-000000000010",
              "inquiry_code":"INQ-GUIDANCE-010",
              "status_code":"AI_GUIDANCE",
              "state_version":3,
              "symptom_summary":"누수 증상",
              "risk_level":"danger",
              "usage_guidance_status":"TOTAL_STOP",
              "usage_guidance_message":"즉시 사용을 중지하세요.",
              "restricted_functions":["전체 사용"],
              "safe_actions":["안전한 곳에서 대기하세요."],
              "escalation_conditions":["누수가 계속되는 경우"],
              "prohibited_actions":["제품 분해"],
              "next_action":"상담 요청",
              "requires_consultation":true,
              "evidence":[],
              "allowed_actions":[{"code":"REQUEST_CONSULTATION"}]
            }
            """.trimIndent()
        )

        val domain = dto.toDomain()
        assertEquals("AI_GUIDANCE", domain.statusCode)
        assertEquals(3, domain.stateVersion)
        assertEquals("TOTAL_STOP", domain.usageGuidanceStatus)
        assertTrue(domain.evidence.isEmpty())
        assertEquals("REQUEST_CONSULTATION", domain.allowedActions.single().code)
    }

    @Test
    fun emptyPublicEvidence_preservesValidatedBackendGuidance() {
        val mapped = GuidanceMapper.map(
            GuidanceData(
                inquiryId = "00000000-0000-4000-8000-000000000011",
                inquiryCode = "INQ-GUIDANCE-011",
                statusCode = "AI_GUIDANCE",
                stateVersion = 4,
                symptomSummary = "온수 온도 이상",
                riskLevel = "caution",
                usageGuidanceStatus = "PARTIAL_STOP",
                usageGuidanceMessage = "온수 기능만 사용을 중지하세요.",
                restrictedFunctions = listOf("온수 출수"),
                safeActions = listOf("냉수만 사용하세요."),
                escalationConditions = listOf("과열이 계속되는 경우"),
                prohibitedActions = listOf("제품 분해"),
                nextAction = "상태 관찰",
                requiresConsultation = false,
                evidence = emptyList(),
                allowedActions = emptyList(),
            )
        )

        assertEquals("AI_GUIDANCE", mapped.statusCode)
        assertEquals(4, mapped.stateVersion)
        assertEquals(UsageGuidanceStatus.PARTIAL_STOP, mapped.usageStatus)
        assertEquals("온수 기능만 사용을 중지하세요.", mapped.usageMessage)
        assertEquals(listOf("온수 출수"), mapped.restrictedFunctions)
        assertEquals(listOf("냉수만 사용하세요."), mapped.safeActions)
        assertEquals("상태 관찰", mapped.nextAction)
        assertFalse(mapped.requiresConsultation)
    }

    @Test
    fun unknownCodes_areMappedToPendingConsultation() {
        val mapped = GuidanceMapper.map(
            GuidanceData(
                inquiryId = "00000000-0000-4000-8000-000000000001",
                inquiryCode = "TEST-001",
                symptomSummary = "unknown",
                riskLevel = "unexpected",
                usageGuidanceStatus = "unexpected",
                usageGuidanceMessage = "unsafe guess",
                safeActions = listOf("guess"),
                prohibitedActions = listOf("do not disassemble"),
                nextAction = "guess",
                requiresConsultation = false,
                evidence = emptyList(),
                allowedActions = listOf(
                    AllowedAction(code = "MARK_RESOLVED"),
                    AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION),
                ),
            )
        )

        assertEquals(RiskLevel.UNKNOWN, mapped.riskLevel)
        assertEquals(UsageGuidanceStatus.PENDING_CONSULTATION, mapped.usageStatus)
        assertTrue(mapped.requiresConsultation)
        assertTrue(mapped.safeActions.isEmpty())
        assertFalse(mapped.allowedActions.any { it.normalizedCode == "MARK_RESOLVED" })
        assertTrue(mapped.allowedActions.any { it.normalizedCode == InquiryActionLabels.REQUEST_CONSULTATION })
    }

    @Test
    fun cautionGuidance_keepsPartialStopAndDoesNotInventDanger() {
        val mapped = GuidanceMapper.map(
            GuidanceData(
                inquiryId = "00000000-0000-4000-8000-000000000003",
                inquiryCode = "TEST-003",
                symptomSummary = "temperature",
                riskLevel = "caution",
                usageGuidanceStatus = "PARTIAL_STOP",
                usageGuidanceMessage = "stop hot water",
                restrictedFunctions = listOf("온수 출수"),
                nextAction = "confirm",
                requiresConsultation = false,
                evidence = listOf(EvidenceCardData("manual", "1", 12, "summary", "VERIFIED", "official")),
                allowedActions = listOf(AllowedAction(code = "CONFIRM_GUIDANCE")),
            )
        )
        assertEquals(RiskLevel.CAUTION, mapped.riskLevel)
        assertEquals(UsageGuidanceStatus.PARTIAL_STOP, mapped.usageStatus)
        assertFalse(mapped.requiresConsultation)
    }

    @Test
    fun dangerGuidance_removesResolveActions() {
        val mapped = GuidanceMapper.map(
            GuidanceData(
                inquiryId = "00000000-0000-4000-8000-000000000002",
                inquiryCode = "TEST-002",
                symptomSummary = "leak",
                riskLevel = "danger",
                usageGuidanceStatus = "TOTAL_STOP",
                usageGuidanceMessage = "stop",
                nextAction = "consult",
                requiresConsultation = true,
                evidence = listOf(
                    EvidenceCardData("manual", "1", 1, "summary", "VERIFIED", "official")
                ),
                allowedActions = listOf(
                    AllowedAction(code = "MARK_RESOLVED"),
                    AllowedAction(code = "CLOSE_INQUIRY"),
                    AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION),
                ),
            )
        )
        assertEquals(listOf(InquiryActionLabels.REQUEST_CONSULTATION), mapped.allowedActions.map { it.normalizedCode })
    }
}
