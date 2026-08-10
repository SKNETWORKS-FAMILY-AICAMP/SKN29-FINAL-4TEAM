package com.skn29.watercare.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SubscriptionModelsTest {
    @Test
    fun summaryMapper_usesOnlyPublicFields_andDoesNotInventSerial() {
        val home = summary().toCustomerHomeData()

        assertEquals("00000000-0000-4000-8000-000000000101", home.subscriptionId)
        assertEquals(P0_SUPPORTED_MODEL_CODE, home.product.modelCode)
        assertEquals("API 미제공", home.product.serialNo)
        assertEquals("방문 관리", home.product.managementTypeLabel)
        assertEquals("2026-08-01", home.lastCareOn)
        assertEquals("미정", home.nextCareOn)
        assertEquals("ACTIVE", home.statusCode)
        assertNull(home.activeInquiry)
        assertTrue(home.isP0SupportedActiveSubscription())
    }

    @Test
    fun detailMapper_preservesNullableCareDates_withoutTimezoneConversion() {
        val detail = SubscriptionDetailDto(
            subscriptionId = summary().subscriptionId,
            statusCode = "ACTIVE",
            managementTypeCode = "SELF_MANAGED",
            startedOn = "2026-07-01",
            lastCareOn = null,
            nextCareOn = "2026-09-03",
            endedOn = null,
            product = summary().product,
        )

        val home = detail.toCustomerHomeData()

        assertNull(home.lastCareOn)
        assertEquals("2026-09-03", home.nextCareOn)
        assertEquals("자가 관리", home.product.managementTypeLabel)
    }

    @Test
    fun inactiveOrUnsupportedSubscription_isNotP0IntakeEligible() {
        val inactive = summary().copy(statusCode = "ENDED").toCustomerHomeData()
        val unsupported = summary().copy(
            product = summary().product.copy(modelCode = "OTHER-MODEL")
        ).toCustomerHomeData()

        assertFalse(inactive.isP0SupportedActiveSubscription())
        assertFalse(unsupported.isP0SupportedActiveSubscription())
    }

    private fun summary() = SubscriptionSummaryDto(
        subscriptionId = "00000000-0000-4000-8000-000000000101",
        statusCode = "ACTIVE",
        managementTypeCode = "VISIT_CARE",
        startedOn = "2026-07-01",
        lastCareOn = "2026-08-01",
        nextCareOn = null,
        product = SubscriptionProductDto(
            productModelId = "00000000-0000-4000-8000-000000000201",
            modelCode = P0_SUPPORTED_MODEL_CODE,
            modelName = "WPU-JAC104D",
            generationCode = "D",
            manufacturer = "SK magic",
        ),
    )
}
