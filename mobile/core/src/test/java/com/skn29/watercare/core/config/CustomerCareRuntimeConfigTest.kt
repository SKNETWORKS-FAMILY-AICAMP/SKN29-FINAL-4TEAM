package com.skn29.watercare.core.config

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CustomerCareRuntimeConfigTest {
    @Test
    fun remoteMode_withCanonicalDemoSubscriptionId_enablesRemoteIntake() {
        val config = CustomerCareRuntimeConfig.from(
            rawMode = "remote",
            rawDemoSubscriptionId = "11111111-2222-4333-8444-555555555555",
        )

        assertEquals(CustomerCareMode.REMOTE, config.mode)
        assertEquals(
            "11111111-2222-4333-8444-555555555555",
            config.demoSubscriptionId,
        )
        assertTrue(config.remoteIntakeAvailable)
    }

    @Test
    fun remoteMode_withoutValidSubscriptionId_blocksRemoteIntake() {
        val config = CustomerCareRuntimeConfig.from(
            rawMode = "REMOTE",
            rawDemoSubscriptionId = "not-a-uuid",
        )

        assertEquals(CustomerCareMode.REMOTE, config.mode)
        assertNull(config.demoSubscriptionId)
        assertFalse(config.remoteIntakeAvailable)
        assertEquals(
            CustomerCareRuntimeConfig.DEFAULT_FIXTURE_SUBSCRIPTION_ID,
            config.fixtureSubscriptionId,
        )
    }

    @Test
    fun fakeMode_doesNotRequireRuntimeSubscriptionId() {
        val config = CustomerCareRuntimeConfig.from(
            rawMode = "FAKE",
            rawDemoSubscriptionId = "",
        )

        assertEquals(CustomerCareMode.FAKE, config.mode)
        assertTrue(config.remoteIntakeAvailable)
    }

    @Test
    fun unknownMode_defaultsToRemoteToPreventSilentFakeFallback() {
        val config = CustomerCareRuntimeConfig.from(
            rawMode = "unexpected",
            rawDemoSubscriptionId = null,
        )

        assertEquals(CustomerCareMode.REMOTE, config.mode)
    }
}
