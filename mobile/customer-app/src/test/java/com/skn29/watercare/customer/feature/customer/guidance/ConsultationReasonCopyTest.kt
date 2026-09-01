package com.skn29.watercare.customer.feature.customer.guidance

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConsultationReasonCopyTest {
    @Test
    fun dangerReason_usesDangerOnlyEmphasis() {
        val copy = consultationReasonCopy("DANGER_DETECTED")

        assertEquals("위험 증상이 감지됐어요", copy.title)
        assertTrue(copy.danger)
    }

    @Test
    fun knownNonDangerReasons_haveDistinctCustomerCopy() {
        val reasons = listOf(
            "NO_EVIDENCE",
            "PRODUCT_VALIDATION_FAILED",
            "AI_PROCESSING_TIMEOUT",
            "AI_CONSULTATION_REQUIRED",
            "CUSTOMER_REQUESTED",
        )

        val copies = reasons.map(::consultationReasonCopy)

        assertEquals(reasons.size, copies.map { it.title }.distinct().size)
        assertTrue(copies.all { !it.danger })
    }

    @Test
    fun unknownReason_fallsBackWithoutDangerPromotion() {
        val copy = consultationReasonCopy("FUTURE_REASON")

        assertEquals("상담이 필요한 상태예요", copy.title)
        assertFalse(copy.danger)
    }
}
