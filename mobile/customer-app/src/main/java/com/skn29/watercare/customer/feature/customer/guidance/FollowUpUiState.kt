package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.CustomerInquiryQuestion
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.InquiryActionLabels

data class FollowUpDraft(
    val text: String = "",
    val selectedOption: String? = null,
)

sealed interface FollowUpUiState {
    data object Disabled : FollowUpUiState
    data object Loading : FollowUpUiState

    data class Empty(val snapshot: CustomerInquirySnapshot) : FollowUpUiState

    data class Form(
        val snapshot: CustomerInquirySnapshot,
        val questions: List<CustomerInquiryQuestion>,
        val drafts: Map<String, FollowUpDraft>,
    ) : FollowUpUiState

    data class Submitting(
        val snapshot: CustomerInquirySnapshot,
        val questions: List<CustomerInquiryQuestion>,
        val drafts: Map<String, FollowUpDraft>,
    ) : FollowUpUiState

    data class Processing(
        val snapshot: CustomerInquirySnapshot,
        val message: String,
        val idempotentReplay: Boolean,
    ) : FollowUpUiState

    data class Success(
        val snapshot: CustomerInquirySnapshot,
        val questions: List<CustomerInquiryQuestion>,
        val drafts: Map<String, FollowUpDraft>,
        val message: String,
        val idempotentReplay: Boolean,
    ) : FollowUpUiState

    data class Conflict(
        val message: String,
        val snapshot: CustomerInquirySnapshot,
        val questions: List<CustomerInquiryQuestion>,
        val drafts: Map<String, FollowUpDraft>,
    ) : FollowUpUiState {
        val canRetry: Boolean
            get() = questions.isNotEmpty() && snapshot.allowedActions.any {
                it.normalizedCode == InquiryActionLabels.SUBMIT_ANSWERS
            }
    }

    data class DuplicateConflict(
        val message: String,
        val snapshot: CustomerInquirySnapshot,
        val questions: List<CustomerInquiryQuestion>,
        val drafts: Map<String, FollowUpDraft>,
    ) : FollowUpUiState

    data class Error(
        val message: String,
        val code: String,
        val httpStatus: Int?,
        val retryable: Boolean,
        val snapshot: CustomerInquirySnapshot? = null,
        val questions: List<CustomerInquiryQuestion> = emptyList(),
        val drafts: Map<String, FollowUpDraft> = emptyMap(),
    ) : FollowUpUiState
}

fun FollowUpUiState.snapshotOrNull(): CustomerInquirySnapshot? = when (this) {
    is FollowUpUiState.Empty -> snapshot
    is FollowUpUiState.Form -> snapshot
    is FollowUpUiState.Submitting -> snapshot
    is FollowUpUiState.Processing -> snapshot
    is FollowUpUiState.Success -> snapshot
    is FollowUpUiState.Conflict -> snapshot
    is FollowUpUiState.DuplicateConflict -> snapshot
    is FollowUpUiState.Error -> snapshot
    FollowUpUiState.Disabled,
    FollowUpUiState.Loading -> null
}
