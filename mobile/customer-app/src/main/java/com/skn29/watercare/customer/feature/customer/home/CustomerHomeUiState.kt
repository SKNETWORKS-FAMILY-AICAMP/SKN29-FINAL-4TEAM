package com.skn29.watercare.customer.feature.customer.home

import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.UserData

data class CustomerHomeUiState(
    val loading: Boolean = true,
    val user: UserData? = null,
    val home: CustomerHomeData? = null,
    val backendAvailable: Boolean? = null,
    val offlinePreview: Boolean = false,
    val customerCareMode: CustomerCareMode = CustomerCareMode.REMOTE,
    val dataSourceLabel: String = "고객 데이터 모드 확인 중",
    val intakeAvailable: Boolean = false,
    val intakeUnavailableReason: String? = null,
    val error: String? = null,
    val loggingOut: Boolean = false,
)
