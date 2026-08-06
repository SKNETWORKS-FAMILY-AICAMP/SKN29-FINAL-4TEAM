package com.skn29.watercare.core.config

import java.util.UUID

enum class CustomerCareMode {
    REMOTE,
    FAKE;

    companion object {
        fun parse(value: String?): CustomerCareMode = when (value?.trim()?.uppercase()) {
            FAKE.name -> FAKE
            else -> REMOTE
        }
    }
}

data class CustomerCareRuntimeConfig(
    val mode: CustomerCareMode,
    val demoSubscriptionId: String?,
) {
    val hasValidDemoSubscriptionId: Boolean
        get() = demoSubscriptionId != null

    val fixtureSubscriptionId: String
        get() = demoSubscriptionId ?: DEFAULT_FIXTURE_SUBSCRIPTION_ID

    val remoteIntakeAvailable: Boolean
        get() = mode == CustomerCareMode.FAKE || hasValidDemoSubscriptionId

    companion object {
        const val DEFAULT_FIXTURE_SUBSCRIPTION_ID = "00000000-0000-4000-8000-000000000101"

        fun from(
            rawMode: String?,
            rawDemoSubscriptionId: String?,
        ): CustomerCareRuntimeConfig = CustomerCareRuntimeConfig(
            mode = CustomerCareMode.parse(rawMode),
            demoSubscriptionId = rawDemoSubscriptionId.toCanonicalUuidOrNull(),
        )

        private fun String?.toCanonicalUuidOrNull(): String? {
            val value = this?.trim()?.takeIf(String::isNotEmpty) ?: return null
            return runCatching { UUID.fromString(value) }
                .getOrNull()
                ?.toString()
                ?.takeIf { it.equals(value, ignoreCase = true) }
        }
    }
}
