package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class ResolutionFeedbackRequestDto(
    @SerialName("state_version")
    val stateVersion: Int,
    val resolved: Boolean = true,
    val comment: String? = null,
)

@Serializable
data class ReportUnresolvedRequestDto(
    @SerialName("state_version")
    val stateVersion: Int,
    val resolved: Boolean = false,
    @SerialName("reason_code")
    val reasonCode: String? = null,
    val comment: String? = null,
)

@Serializable
data class ResolutionTransitionResponseDto(
    val message: String,
    @SerialName("inquiry_id")
    val inquiryId: String,
    val status: String,
    @SerialName("state_version")
    val stateVersion: Int,
    @SerialName("allowed_actions")
    val allowedActions: List<AllowedAction> = emptyList(),
    @SerialName("idempotent_replay")
    val idempotentReplay: Boolean,
    val resource: JsonElement? = null,
)
