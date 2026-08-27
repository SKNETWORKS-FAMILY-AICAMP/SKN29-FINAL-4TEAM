package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.CustomerInquiryConsultationResult
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.GuidanceDisplayModel
import com.skn29.watercare.core.model.ResolutionTransitionResponseDto

data class CustomerWorkflowUiSnapshot(
    val statusCode: String,
    val stateVersion: Int,
    val allowedActions: List<AllowedAction>,
)

fun CustomerInquirySnapshot.toWorkflowUiSnapshot() =
    CustomerWorkflowUiSnapshot(
        statusCode = statusCode,
        stateVersion = stateVersion,
        allowedActions = allowedActions,
    )

fun CustomerInquiryConsultationResult.toWorkflowUiSnapshot() =
    CustomerWorkflowUiSnapshot(
        statusCode = statusCode,
        stateVersion = stateVersion,
        allowedActions = allowedActions,
    )

fun ResolutionTransitionResponseDto.toWorkflowUiSnapshot() =
    CustomerWorkflowUiSnapshot(
        statusCode = status,
        stateVersion = stateVersion,
        allowedActions = allowedActions,
    )

sealed interface GuidanceUiState {
    data object Loading : GuidanceUiState
    data class Content(val guidance: GuidanceDisplayModel) : GuidanceUiState
    data class NoEvidence(val guidance: GuidanceDisplayModel) : GuidanceUiState
    data class ConsultationResult(
        val result: CustomerInquiryConsultationResult,
    ) : GuidanceUiState
    data class ConsultationResultNotReady(
        val message: String,
    ) : GuidanceUiState
    data class NotReady(val message: String) : GuidanceUiState
    data class AiFailure(val message: String, val retryable: Boolean) : GuidanceUiState
    data class NetworkFailure(val message: String, val retryable: Boolean) : GuidanceUiState
    data class Error(val message: String, val retryable: Boolean) : GuidanceUiState
}
