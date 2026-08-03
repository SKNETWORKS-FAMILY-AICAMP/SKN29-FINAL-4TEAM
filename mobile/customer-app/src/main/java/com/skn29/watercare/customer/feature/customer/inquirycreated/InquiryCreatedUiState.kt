package com.skn29.watercare.customer.feature.customer.inquirycreated

import com.skn29.watercare.core.model.InquiryRuntimeSnapshot

data class InquiryCreatedUiState(
    val loading: Boolean = true,
    val inquiry: InquiryRuntimeSnapshot? = null,
    val cancelling: Boolean = false,
    val error: String? = null,
    val retryable: Boolean = false,
    val correlationId: String? = null,
)
