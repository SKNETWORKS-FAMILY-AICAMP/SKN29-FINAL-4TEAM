package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.InquiryActionLabels

sealed interface ConsultationRequestUiState {
    data object Idle : ConsultationRequestUiState
    data object Requesting : ConsultationRequestUiState

    data class Success(
        val message: String,
        val snapshot: CustomerInquirySnapshot,
        val idempotentReplay: Boolean,
    ) : ConsultationRequestUiState

    data class Conflict(
        val message: String,
        val snapshot: CustomerInquirySnapshot,
    ) : ConsultationRequestUiState {
        val canRetry: Boolean
            get() = snapshot.allowedActions.any {
                it.normalizedCode ==
                    InquiryActionLabels.REQUEST_CONSULTATION
            }
    }

    data class Error(
        val message: String,
        val retryable: Boolean,
    ) : ConsultationRequestUiState
}