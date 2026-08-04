package com.skn29.watercare.customer.feature.customer.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.config.CustomerCareRuntimeConfig
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.CustomerCareRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CustomerHomeViewModel(
    private val authRepository: AuthRepository,
    private val careRepository: CustomerCareRepository,
    private val backendStatusRepository: BackendStatusRepository,
    private val runtimeConfig: CustomerCareRuntimeConfig,
    offlinePreview: Boolean,
) : ViewModel() {
    private val initialRuntimeState = resolveRuntimeState(offlinePreview)
    private val _state = MutableStateFlow(
        CustomerHomeUiState(
            offlinePreview = offlinePreview,
            customerCareMode = runtimeConfig.mode,
            dataSourceLabel = initialRuntimeState.dataSourceLabel,
            intakeAvailable = initialRuntimeState.intakeAvailable,
            intakeUnavailableReason = initialRuntimeState.intakeUnavailableReason,
        )
    )
    val state: StateFlow<CustomerHomeUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)

            val offlinePreview = _state.value.offlinePreview
            val runtimeState = resolveRuntimeState(offlinePreview)
            val homeDeferred = async { careRepository.getHome() }
            val healthDeferred =
                if (offlinePreview) null else async { backendStatusRepository.health() }
            val userDeferred =
                if (offlinePreview) null else async { authRepository.me() }

            val home = homeDeferred.await()
            val health = healthDeferred?.await()
            val user = userDeferred?.await()

            val error = when {
                home is ApiResult.Failure -> home.message
                user is ApiResult.Failure -> user.message
                else -> null
            }
            val homeData = when (home) {
                is ApiResult.Success -> home.value
                is ApiResult.Failure -> null
            }
            val userData = when (user) {
                is ApiResult.Success -> user.value
                else -> null
            }

            _state.value = _state.value.copy(
                loading = false,
                home = homeData,
                user = userData,
                backendAvailable =
                    if (offlinePreview) false else health is ApiResult.Success<*>,
                dataSourceLabel = runtimeState.dataSourceLabel,
                intakeAvailable = runtimeState.intakeAvailable && homeData != null,
                intakeUnavailableReason = when {
                    homeData == null -> "고객 홈 정보를 불러온 뒤 문의를 시작할 수 있습니다."
                    else -> runtimeState.intakeUnavailableReason
                },
                error = error,
            )
        }
    }

    fun logout(onDone: () -> Unit) {
        if (_state.value.loggingOut) return
        viewModelScope.launch {
            _state.value = _state.value.copy(loggingOut = true)
            if (!_state.value.offlinePreview) authRepository.logout()
            onDone()
        }
    }

    private fun resolveRuntimeState(offlinePreview: Boolean): RuntimeState = when {
        runtimeConfig.mode == CustomerCareMode.FAKE -> RuntimeState(
            dataSourceLabel = "Demo Mock 모드 · 홈·문의·안내 합성 데이터",
            intakeAvailable = true,
            intakeUnavailableReason = null,
        )

        offlinePreview -> RuntimeState(
            dataSourceLabel = "오프라인 미리보기 · 홈·안내 합성 Fixture · 문의 전송 차단",
            intakeAvailable = false,
            intakeUnavailableReason =
                "Remote 모드의 오프라인 미리보기에서는 실제 문의를 전송하지 않습니다. " +
                    "전체 Mock 흐름은 CUSTOMER_CARE_MODE=FAKE로 실행하세요.",
        )

        runtimeConfig.hasValidDemoSubscriptionId -> RuntimeState(
            dataSourceLabel = "Remote 모드 · 문의 생성·제출 실제 API · 홈·안내 합성 Fixture",
            intakeAvailable = true,
            intakeUnavailableReason = null,
        )

        else -> RuntimeState(
            dataSourceLabel = "Remote 모드 · Demo 구독 UUID 미설정 · 홈·안내 합성 Fixture",
            intakeAvailable = false,
            intakeUnavailableReason =
                "mobile/local.properties의 DEMO_SUBSCRIPTION_ID에 " +
                    "Demo 고객의 실제 활성 구독 Public UUID를 입력하세요.",
        )
    }

    private data class RuntimeState(
        val dataSourceLabel: String,
        val intakeAvailable: Boolean,
        val intakeUnavailableReason: String?,
    )
}
