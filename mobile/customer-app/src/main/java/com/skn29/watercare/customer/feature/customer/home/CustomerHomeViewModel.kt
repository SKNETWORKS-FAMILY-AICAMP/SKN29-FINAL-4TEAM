package com.skn29.watercare.customer.feature.customer.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.config.CustomerCareRuntimeConfig
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.model.isP0SupportedActiveSubscription
import com.skn29.watercare.core.model.toCustomerHomeData
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.CustomerInquiryRepository
import com.skn29.watercare.core.repository.SubscriptionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CustomerHomeViewModel(
    private val authRepository: AuthRepository,
    private val careRepository: CustomerCareRepository,
    private val subscriptionRepository: SubscriptionRepository? = null,
    private val customerInquiryRepository: CustomerInquiryRepository? = null,
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
            _state.value = _state.value.copy(
                loading = true,
                error = null,
                errorCode = null,
                errorHttpStatus = null,
            )

            val offlinePreview = _state.value.offlinePreview
            val runtimeState = resolveRuntimeState(offlinePreview)
            val localFixture =
                runtimeConfig.mode ==
                    CustomerCareMode.FAKE

            val health =
                if (offlinePreview || localFixture) {
                    null
                } else {
                    backendStatusRepository.health()
                }

            val user =
                if (offlinePreview || localFixture) {
                    null
                } else {
                    authRepository.me()
                }

            if (
                runtimeConfig.mode == CustomerCareMode.REMOTE &&
                !offlinePreview &&
                subscriptionRepository != null
            ) {
                loadRemoteSubscriptions(
                    runtimeState = runtimeState,
                    health = health,
                    user = user,
                )
            } else {
                loadFixtureOrPreview(
                    runtimeState = runtimeState,
                    health = health,
                    user = user,
                )
            }
        }
    }

    private suspend fun loadRemoteSubscriptions(
        runtimeState: RuntimeState,
        health: ApiResult<Unit>?,
        user: ApiResult<UserData>?,
    ) {
        val repository = subscriptionRepository
            ?: return publishFailure(
                failure = ApiResult.Failure(
                    code = "SUBSCRIPTION_REPOSITORY_MISSING",
                    message = "구독 조회 구성이 준비되지 않았습니다.",
                ),
                runtimeState = runtimeState,
                health = health,
                user = user,
            )

        when (val listResult = repository.list()) {
            is ApiResult.Failure -> publishFailure(
                failure = listResult,
                runtimeState = runtimeState,
                health = health,
                user = user,
            )

            is ApiResult.Success -> {
                val subscriptions = listResult.value.items.map { it.toCustomerHomeData() }

                val activeInquiryResult =
                    customerInquiryRepository?.activeInquiry()

                if (activeInquiryResult is ApiResult.Failure) {
                    publishFailure(
                        failure = activeInquiryResult,
                        runtimeState = runtimeState,
                        health = health,
                        user = user,
                    )
                    return
                }

                val activeInquiry =
                    (activeInquiryResult as? ApiResult.Success)?.value

                if (subscriptions.isEmpty()) {
                    _state.value = _state.value.copy(
                        loading = false,
                        user = user.successValue(),
                        home = null,
                        activeInquiry = activeInquiry,
                        subscriptions = emptyList(),
                        selectedSubscriptionId = null,
                        backendAvailable = health is ApiResult.Success<*>,
                        dataSourceLabel = runtimeState.dataSourceLabel,
                        intakeAvailable = false,
                        intakeUnavailableReason = "현재 문의를 시작할 수 있는 구독이 없습니다.",
                        error = null,
                        errorCode = "SUBSCRIPTION_EMPTY",
                        errorHttpStatus = null,
                    )
                    return
                }

                val previousSelection = _state.value.selectedSubscriptionId
                val selectedSummary = subscriptions.firstOrNull {
                    it.subscriptionId == activeInquiry?.subscriptionId
                } ?: subscriptions.firstOrNull {
                    it.subscriptionId == previousSelection
                } ?: subscriptions.firstOrNull {
                    it.isP0SupportedActiveSubscription()
                } ?: subscriptions.first()

                loadSelectedDetail(
                    selectedId = selectedSummary.subscriptionId,
                    subscriptions = subscriptions,
                    runtimeState = runtimeState,
                    health = health,
                    user = user,
                    initialLoad = true,
                    activeInquiry = activeInquiry,
                )
            }
        }
    }

    private suspend fun loadSelectedDetail(
        selectedId: String,
        subscriptions: List<CustomerHomeData>,
        runtimeState: RuntimeState,
        health: ApiResult<Unit>?,
        user: ApiResult<UserData>?,
        initialLoad: Boolean,
        activeInquiry: CustomerInquirySnapshot?,
    ) {
        val repository = subscriptionRepository ?: return
        val summary = subscriptions.firstOrNull { it.subscriptionId == selectedId }

        when (val detailResult = repository.detail(selectedId)) {
            is ApiResult.Failure -> {
                val userFailure = user as? ApiResult.Failure
                val effectiveFailure = userFailure ?: detailResult
                _state.value = _state.value.copy(
                    loading = false,
                    selectingSubscription = false,
                    user = user.successValue(),
                    home = if (initialLoad) summary else _state.value.home,
                    activeInquiry = activeInquiry,
                    subscriptions = subscriptions,
                    selectedSubscriptionId = if (initialLoad) {
                        summary?.subscriptionId
                    } else {
                        _state.value.selectedSubscriptionId
                    },
                    backendAvailable = health is ApiResult.Success<*>,
                    dataSourceLabel = runtimeState.dataSourceLabel,
                    intakeAvailable = false,
                    intakeUnavailableReason = "구독 상세 정보를 확인한 뒤 문의를 시작할 수 있습니다.",
                    error = effectiveFailure.message,
                    errorCode = effectiveFailure.code,
                    errorHttpStatus = effectiveFailure.httpStatus,
                )
            }

            is ApiResult.Success -> {
                val selectedHome = detailResult.value.toCustomerHomeData()
                val userFailure = user as? ApiResult.Failure
                val supportReason = supportReason(selectedHome)
                _state.value = _state.value.copy(
                    loading = false,
                    selectingSubscription = false,
                    user = user.successValue(),
                    home = selectedHome,
                    activeInquiry = activeInquiry,
                    subscriptions = subscriptions,
                    selectedSubscriptionId = selectedHome.subscriptionId,
                    backendAvailable = health is ApiResult.Success<*>,
                    dataSourceLabel = runtimeState.dataSourceLabel,
                    intakeAvailable =
                        runtimeState.intakeAvailable &&
                            supportReason == null &&
                            userFailure == null,
                    intakeUnavailableReason = userFailure?.message ?: supportReason,
                    error = userFailure?.message,
                    errorCode = userFailure?.code,
                    errorHttpStatus = userFailure?.httpStatus,
                )
            }
        }
    }

    private suspend fun loadFixtureOrPreview(
        runtimeState: RuntimeState,
        health: ApiResult<Unit>?,
        user: ApiResult<UserData>?,
    ) {
        val home = careRepository.getHome()
        val homeData = (home as? ApiResult.Success)?.value
        val homeFailure = home as? ApiResult.Failure
        val userFailure = user as? ApiResult.Failure
        val effectiveFailure = homeFailure ?: userFailure

        _state.value = _state.value.copy(
            loading = false,
            home = homeData,
            activeInquiry = null,
            subscriptions = listOfNotNull(homeData),
            selectedSubscriptionId = homeData?.subscriptionId,
            user = user.successValue(),
            backendAvailable =
                when {
                    runtimeConfig.mode ==
                        CustomerCareMode.FAKE -> false

                    _state.value.offlinePreview -> false

                    else ->
                        health is ApiResult.Success<*>
                },
            dataSourceLabel = runtimeState.dataSourceLabel,
            intakeAvailable =
                runtimeState.intakeAvailable &&
                    homeData != null &&
                    effectiveFailure == null,
            intakeUnavailableReason = when {
                effectiveFailure != null -> effectiveFailure.message
                homeData == null -> "고객 홈 정보를 불러온 뒤 문의를 시작할 수 있습니다."
                else -> runtimeState.intakeUnavailableReason
            },
            error = effectiveFailure?.message,
            errorCode = effectiveFailure?.code,
            errorHttpStatus = effectiveFailure?.httpStatus,
        )
    }

    fun selectSubscription(subscriptionId: String) {
        if (
            runtimeConfig.mode != CustomerCareMode.REMOTE ||
            _state.value.offlinePreview ||
            _state.value.loading ||
            _state.value.selectingSubscription ||
            _state.value.loggingOut ||
            subscriptionId == _state.value.selectedSubscriptionId
        ) {
            return
        }

        val subscriptions = _state.value.subscriptions
        if (subscriptions.none { it.subscriptionId == subscriptionId }) return

        viewModelScope.launch {
            _state.value = _state.value.copy(
                selectingSubscription = true,
                error = null,
                errorCode = null,
                errorHttpStatus = null,
            )
            val runtimeState = resolveRuntimeState(offlinePreview = false)
            val health = backendStatusRepository.health()
            val user = authRepository.me()
            loadSelectedDetail(
                selectedId = subscriptionId,
                subscriptions = subscriptions,
                runtimeState = runtimeState,
                health = health,
                user = user,
                initialLoad = false,
                activeInquiry = _state.value.activeInquiry,
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

        else -> RuntimeState(
            dataSourceLabel = "Remote 모드 · 구독 목록·상세·문의 실제 API · 안내 API 미제공 시 차단",
            intakeAvailable = true,
            intakeUnavailableReason = null,
        )
    }

    private fun supportReason(home: CustomerHomeData): String? = when {
        home.statusCode != "ACTIVE" ->
            "현재 이용 중인 정수기에서만 문의를 시작할 수 있어요."

        home.product.modelCode != com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE ->
            "이 정수기는 현재 문의 기능을 이용할 수 없어요."

        else -> null
    }

    private fun ApiResult<UserData>?.successValue(): UserData? =
        (this as? ApiResult.Success)?.value

    private fun publishFailure(
        failure: ApiResult.Failure,
        runtimeState: RuntimeState,
        health: ApiResult<Unit>?,
        user: ApiResult<UserData>?,
    ) {
        val userFailure = user as? ApiResult.Failure
        val effectiveFailure = userFailure ?: failure
        _state.value = _state.value.copy(
            loading = false,
            user = user.successValue(),
            home = null,
            activeInquiry = null,
            subscriptions = emptyList(),
            selectedSubscriptionId = null,
            backendAvailable = health is ApiResult.Success<*>,
            dataSourceLabel = runtimeState.dataSourceLabel,
            intakeAvailable = false,
            intakeUnavailableReason = effectiveFailure.message,
            error = effectiveFailure.message,
            errorCode = effectiveFailure.code,
            errorHttpStatus = effectiveFailure.httpStatus,
        )
    }

    private data class RuntimeState(
        val dataSourceLabel: String,
        val intakeAvailable: Boolean,
        val intakeUnavailableReason: String?,
    )
}
