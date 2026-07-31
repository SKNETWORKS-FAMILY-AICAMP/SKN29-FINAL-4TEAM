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
                allowedActions = listOf("MARK_RESOLVED", "REQUEST_CONSULTATION"),
            )
        )

        assertEquals(RiskLevel.UNKNOWN, mapped.riskLevel)
        assertEquals(UsageGuidanceStatus.PENDING_CONSULTATION, mapped.usageStatus)
        assertTrue(mapped.requiresConsultation)
        assertTrue(mapped.safeActions.isEmpty())
        assertFalse("MARK_RESOLVED" in mapped.allowedActions)
        assertTrue("REQUEST_CONSULTATION" in mapped.allowedActions)
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
                allowedActions = listOf("CONFIRM_GUIDANCE"),
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
                allowedActions = listOf("MARK_RESOLVED", "CLOSE_INQUIRY", "REQUEST_CONSULTATION"),
            )
        )
        assertEquals(listOf("REQUEST_CONSULTATION"), mapped.allowedActions)
    }
}
