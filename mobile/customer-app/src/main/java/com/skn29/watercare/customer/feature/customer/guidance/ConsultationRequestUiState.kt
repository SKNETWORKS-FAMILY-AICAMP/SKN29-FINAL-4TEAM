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
    ) : ConsultationRequestUiState {
        val inquiryId: String get() = snapshot.inquiryId
        val statusCode: String get() = snapshot.statusCode
        val stateVersion: Int get() = snapshot.stateVersion
        val allowedActions get() = snapshot.allowedActions
    }

    data class Conflict(
        val message: String,
        val snapshot: CustomerInquirySnapshot,
    ) : ConsultationRequestUiState {
        val currentStatus: String get() = snapshot.statusCode
        val currentStateVersion: Int get() = snapshot.stateVersion
        val allowedActions get() = snapshot.allowedActions

        val canRetry: Boolean
            get() = snapshot.allowedActions.any {
                it.normalizedCode ==
                    InquiryActionLabels.REQUEST_CONSULTATION
            }
    }

    data class Error(
        val message: String,
        val retryable: Boolean,
        val code: String = "CONSULTATION_REQUEST_ERROR",
        val httpStatus: Int? = null,
    ) : ConsultationRequestUiState
}
