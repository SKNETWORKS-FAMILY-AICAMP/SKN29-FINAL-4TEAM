package com.skn29.watercare.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CareModelsTest {
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
