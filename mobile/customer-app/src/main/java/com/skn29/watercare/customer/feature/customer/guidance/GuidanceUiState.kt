package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.GuidanceDisplayModel

sealed interface GuidanceUiState {
    data object Loading : GuidanceUiState
    data class Content(val guidance: GuidanceDisplayModel) : GuidanceUiState
    data class NoEvidence(val guidance: GuidanceDisplayModel) : GuidanceUiState
    data class AiFailure(
        val message: String,
        val retryable: Boolean,
        val statusCode: String? = null,
        val stateVersion: Int? = null,
        val allowedActions: List<AllowedAction> = emptyList(),
    ) : GuidanceUiState
    data class NetworkFailure(val message: String, val retryable: Boolean) : GuidanceUiState
    data class Error(val message: String, val retryable: Boolean) : GuidanceUiState
}
