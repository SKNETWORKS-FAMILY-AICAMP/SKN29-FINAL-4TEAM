package com.skn29.watercare.customer.feature.customer.care

import com.skn29.watercare.core.model.CareHistoryItemDto
import com.skn29.watercare.core.model.CustomerSelfCareType
import com.skn29.watercare.core.model.SubscriptionSummaryDto

enum class CareHistoryErrorKind {
    AUTH_EXPIRED,
    NOT_FOUND,
    CONFLICT,
    VALIDATION,
    NETWORK,
    SERVER,
    UNKNOWN,
}

data class CareHistoryUiState(
    val loadingSubscriptions: Boolean = true,
    val loadingHistory: Boolean = false,
    val subscriptions: List<SubscriptionSummaryDto> = emptyList(),
    val selectedSubscriptionId: String? = null,
    val items: List<CareHistoryItemDto> = emptyList(),
    val selectedCareType: CustomerSelfCareType =
        CustomerSelfCareType.FILTER_REPLACEMENT,
    val performedOn: String = "",
    val isCreating: Boolean = false,
    val detail: CareHistoryItemDto? = null,
    val notice: String? = null,
    val errorKind: CareHistoryErrorKind? = null,
    val errorMessage: String? = null,
    val authExpired: Boolean = false,
)