package com.skn29.watercare.customer.navigation

import android.net.Uri
import com.skn29.watercare.core.model.AllowedAction

object CustomerRoute {
    const val LOGIN = "login"
    const val HOME = "home?offline={offline}"
    const val CARE = "care"
    const val CARE_PRECHECK = "care-precheck/{subscriptionId}"

    const val INTAKE =
        "intake/{subscriptionId}" +
            "?fixturePreview={fixturePreview}" +
            "&initialTopic={initialTopic}" +
            "&initialRawText={initialRawText}"

    const val FOLLOW_UP =
        "follow-up/{inquiryId}/{scenario}" +
            "?inquiryCode={inquiryCode}" +
            "&idempotentReplay={idempotentReplay}"

    const val GUIDANCE =
        "guidance/{inquiryId}/{scenario}" +
            "?inquiryCode={inquiryCode}" +
            "&statusCode={statusCode}" +
            "&stateVersion={stateVersion}" +
            "&idempotentReplay={idempotentReplay}" +
            "&allowedActions={allowedActions}" +
            "&fixturePreview={fixturePreview}"

    fun home(
        offline: Boolean,
    ) =
        "home?offline=$offline"

    fun carePrecheck(
        subscriptionId: String,
    ): String =
        "care-precheck/${Uri.encode(subscriptionId)}"

    fun intake(
        subscriptionId: String,
        fixturePreview: Boolean = false,
        initialTopic: String = "",
        initialRawText: String = "",
    ) =
        buildString {
            append("intake/")
            append(
                Uri.encode(
                    subscriptionId
                )
            )
            append(
                "?fixturePreview="
            )
            append(
                fixturePreview
            )
            append(
                "&initialTopic="
            )
            append(
                Uri.encode(
                    initialTopic
                )
            )
            append(
                "&initialRawText="
            )
            append(
                Uri.encode(
                    initialRawText
                )
            )
        }

    fun followUp(
        inquiryId: String,
        scenario: String,
        inquiryCode: String = "",
        idempotentReplay:
            Boolean? = null,
    ): String =
        buildString {
            append("follow-up/")
            append(
                Uri.encode(
                    inquiryId
                )
            )
            append("/")
            append(
                Uri.encode(
                    scenario
                )
            )
            append(
                "?inquiryCode="
            )
            append(
                Uri.encode(
                    inquiryCode
                )
            )
            append(
                "&idempotentReplay="
            )
            append(
                idempotentReplay
                    ?: false
            )
        }

    fun guidance(
        inquiryId: String,
        scenario: String,
        inquiryCode: String = "",
        statusCode: String? = null,
        stateVersion: Int? = null,
        idempotentReplay:
            Boolean? = null,
        allowedActions:
            List<AllowedAction> =
            emptyList(),
        fixturePreview:
            Boolean = false,
    ): String {
        val actionCodes =
            allowedActions
                .map(
                    AllowedAction::
                        normalizedCode
                )
                .filter(
                    String::isNotEmpty
                )
                .distinct()
                .joinToString(",")

        return buildString {
            append("guidance/")
            append(
                Uri.encode(
                    inquiryId
                )
            )
            append("/")
            append(
                Uri.encode(
                    scenario
                )
            )
            append(
                "?inquiryCode="
            )
            append(
                Uri.encode(
                    inquiryCode
                )
            )
            append(
                "&statusCode="
            )
            append(
                Uri.encode(
                    statusCode
                        .orEmpty()
                )
            )
            append(
                "&stateVersion="
            )
            append(
                stateVersion ?: -1
            )
            append(
                "&idempotentReplay="
            )
            append(
                idempotentReplay
                    ?: false
            )
            append(
                "&allowedActions="
            )
            append(
                Uri.encode(
                    actionCodes
                )
            )
            append(
                "&fixturePreview="
            )
            append(
                fixturePreview
            )
        }
    }
}