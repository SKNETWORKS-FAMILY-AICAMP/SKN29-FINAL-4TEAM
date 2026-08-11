package com.skn29.watercare.technician

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class TechnicianStatusMappingTest {
    @Test
    fun waitingCompletion_remainsWaitingCompletion_notCompleted() {
        val visit = visitWithStatus("WAITING_COMPLETION")

        assertEquals("완료 대기", visit.scheduleStatusLabel)
        assertNotEquals("완료", visit.scheduleStatusLabel)
    }

    @Test
    fun completed_isNotGuessedWithoutCanonicalMobileContract() {
        val visit = visitWithStatus("COMPLETED")

        assertEquals("상태 확인 필요", visit.scheduleStatusLabel)
    }

    @Test
    fun unknownLegacyStatus_failsClosed() {
        val visit = visitWithStatus("LEGACY_UNKNOWN_STATE")

        assertEquals("상태 확인 필요", visit.scheduleStatusLabel)
    }

    private fun visitWithStatus(
        scheduleStatusCode: String,
    ) = TechnicianVisitSummary(
        visitId = "00000000-0000-4000-8000-000000009999",
        visitCode = "TEST-VISIT",
        customerMaskedName = "테○○",
        maskedAddress = "서울시 ***",
        productModel = "WPU-JAC104D",
        scheduledAt = "2026-08-11 10:30",
        scheduleStatusCode = scheduleStatusCode,
        symptomSummary = "상태 매핑 회귀 테스트",
        risk = TechnicianVisitRisk.UNKNOWN,
        usageRestrictionLabel = "확인 필요",
        scenarioId = "TEST-STATUS-MAPPING",
    )
}
