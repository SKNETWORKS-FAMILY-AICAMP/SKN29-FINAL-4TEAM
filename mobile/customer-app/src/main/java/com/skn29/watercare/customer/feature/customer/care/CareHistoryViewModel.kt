package com.skn29.watercare.customer.feature.customer.care

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CareHistoryCreateRequestDto
import com.skn29.watercare.core.model.CareHistoryItemDto
import com.skn29.watercare.core.model.CustomerSelfCareType
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.SubscriptionSummaryDto
import com.skn29.watercare.core.model.toCareHistoryItem
import com.skn29.watercare.core.repository.CareHistoryRepository
import com.skn29.watercare.core.repository.SubscriptionRepository
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CareHistoryViewModel(
    private val subscriptionRepository: SubscriptionRepository,
    private val careHistoryRepository: CareHistoryRepository,
    private val todayProvider: () -> LocalDate = {
        LocalDate.now()
    },
) : ViewModel() {
    private val _state = MutableStateFlow(
        CareHistoryUiState(
            performedOn = todayProvider().toString(),
        )
    )
    val state: StateFlow<CareHistoryUiState> =
        _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(
                loadingSubscriptions = true,
                loadingHistory = false,
                errorKind = null,
                errorMessage = null,
                authExpired = false,
            )

            when (
                val result =
                    subscriptionRepository.list(
                        page = 1,
                        size = 100,
                    )
            ) {
                is ApiResult.Success -> {
                    val eligible =
                        result.value.items
                            .filter(
                                ::isEligibleSubscription
                            )

                    val selected =
                        _state.value
                            .selectedSubscriptionId
                            ?.takeIf { id ->
                                eligible.any {
                                    it.subscriptionId ==
                                        id
                                }
                            }
                            ?: eligible.firstOrNull()
                                ?.subscriptionId

                    _state.value =
                        _state.value.copy(
                            loadingSubscriptions = false,
                            subscriptions = eligible,
                            selectedSubscriptionId =
                                selected,
                            items = if (
                                selected == null
                            ) {
                                emptyList()
                            } else {
                                _state.value.items
                            },
                            detail = null,
                        )

                    if (selected != null) {
                        loadHistoryInternal(
                            subscriptionId = selected,
                            preserveNotice = false,
                        )
                    }
                }

                is ApiResult.Failure -> {
                    applyFailure(result)
                }
            }
        }
    }

    fun selectSubscription(
        subscriptionId: String,
    ) {
        val allowed =
            _state.value.subscriptions.any {
                it.subscriptionId == subscriptionId
            }
        if (!allowed) {
            setLocalValidationError(
                "선택할 수 없는 구독입니다."
            )
            return
        }

        if (
            _state.value.selectedSubscriptionId ==
            subscriptionId
        ) {
            return
        }

        _state.value = _state.value.copy(
            selectedSubscriptionId =
                subscriptionId,
            detail = null,
            notice = null,
            errorKind = null,
            errorMessage = null,
        )

        viewModelScope.launch {
            loadHistoryInternal(
                subscriptionId =
                    subscriptionId,
                preserveNotice = false,
            )
        }
    }

    fun selectCareType(
        careType: CustomerSelfCareType,
    ) {
        _state.value = _state.value.copy(
            selectedCareType = careType,
            notice = null,
            errorKind = null,
            errorMessage = null,
        )
    }

    fun updatePerformedOn(
        value: String,
    ) {
        _state.value = _state.value.copy(
            performedOn = value.take(10),
            notice = null,
            errorKind = null,
            errorMessage = null,
        )
    }

    fun createCareRecord() {
        val snapshot = _state.value
        if (snapshot.isCreating) return

        val subscriptionId =
            snapshot.selectedSubscriptionId
        if (subscriptionId == null) {
            setLocalValidationError(
                "등록 가능한 정수기를 선택해주세요."
            )
            return
        }

        val subscription =
            snapshot.subscriptions
                .firstOrNull {
                    it.subscriptionId ==
                        subscriptionId
                }
        if (subscription == null) {
            setLocalValidationError(
                "등록 가능한 정수기를 선택해주세요."
            )
            return
        }

        val performedOn =
            parseDate(snapshot.performedOn)
        if (performedOn == null) {
            setLocalValidationError(
                "관리일을 YYYY-MM-DD 형식으로 입력해주세요."
            )
            return
        }

        if (performedOn > todayProvider()) {
            setLocalValidationError(
                "미래 날짜는 등록할 수 없습니다."
            )
            return
        }

        val startedOn =
            parseDate(subscription.startedOn)
        if (
            startedOn != null &&
            performedOn < startedOn
        ) {
            setLocalValidationError(
                "구독 시작일보다 이전 날짜는 등록할 수 없습니다."
            )
            return
        }

        _state.value = snapshot.copy(
            isCreating = true,
            notice = null,
            errorKind = null,
            errorMessage = null,
        )

        viewModelScope.launch {
            val request =
                CareHistoryCreateRequestDto(
                    careTypeCode =
                        snapshot
                            .selectedCareType
                            .code,
                    performedOn =
                        performedOn.toString(),
                )

            when (
                val result =
                    careHistoryRepository.create(
                        subscriptionId =
                            subscriptionId,
                        request = request,
                    )
            ) {
                is ApiResult.Success -> {
                    val item =
                        result.value
                            .toCareHistoryItem()

                    _state.value =
                        _state.value.copy(
                            isCreating = false,
                            detail = item,
                            notice =
                                if (
                                    result.value
                                        .idempotentReplay
                                ) {
                                    "이미 처리된 동일 요청을 안전하게 다시 확인했습니다."
                                } else {
                                    "케어 이력이 등록되었습니다."
                                },
                            errorKind = null,
                            errorMessage = null,
                        )

                    loadHistoryInternal(
                        subscriptionId =
                            subscriptionId,
                        preserveNotice = true,
                    )
                }

                is ApiResult.Failure -> {
                    _state.value =
                        _state.value.copy(
                            isCreating = false,
                        )
                    applyFailure(result)
                }
            }
        }
    }

    fun openDetail(
        careRecordId: String,
    ) {
        val subscriptionId =
            _state.value
                .selectedSubscriptionId
                ?: return

        viewModelScope.launch {
            when (
                val result =
                    careHistoryRepository.detail(
                        subscriptionId =
                            subscriptionId,
                        careRecordId =
                            careRecordId,
                    )
            ) {
                is ApiResult.Success -> {
                    val item =
                        result.value
                            .takeIf {
                                it.statusCode ==
                                    "COMPLETED" &&
                                    it.subscriptionId ==
                                    subscriptionId
                            }

                    if (item == null) {
                        setLocalNotFound()
                    } else {
                        _state.value =
                            _state.value.copy(
                                detail = item,
                                errorKind = null,
                                errorMessage = null,
                            )
                    }
                }

                is ApiResult.Failure -> {
                    applyFailure(result)
                }
            }
        }
    }

    fun consumeAuthExpired() {
        if (_state.value.authExpired) {
            _state.value =
                _state.value.copy(
                    authExpired = false,
                )
        }
    }

    private suspend fun loadHistoryInternal(
        subscriptionId: String,
        preserveNotice: Boolean,
    ) {
        _state.value = _state.value.copy(
            loadingHistory = true,
            errorKind = null,
            errorMessage = null,
            notice =
                if (preserveNotice) {
                    _state.value.notice
                } else {
                    null
                },
        )

        when (
            val result =
                careHistoryRepository.list(
                    subscriptionId =
                        subscriptionId,
                    page = 1,
                    size = 100,
                )
        ) {
            is ApiResult.Success -> {
                val safeItems =
                    result.value.items
                        .filter {
                            it.statusCode ==
                                "COMPLETED" &&
                                it.subscriptionId ==
                                subscriptionId
                        }

                _state.value =
                    _state.value.copy(
                        loadingSubscriptions =
                            false,
                        loadingHistory = false,
                        items = safeItems,
                        errorKind = null,
                        errorMessage = null,
                    )
            }

            is ApiResult.Failure -> {
                applyFailure(result)
            }
        }
    }

    private fun applyFailure(
        failure: ApiResult.Failure,
    ) {
        val httpStatus = failure.httpStatus
        val kind =
            when {
                httpStatus == 401 ->
                    CareHistoryErrorKind
                        .AUTH_EXPIRED

                httpStatus == 404 ->
                    CareHistoryErrorKind
                        .NOT_FOUND

                httpStatus == 409 ->
                    CareHistoryErrorKind
                        .CONFLICT

                httpStatus == 400 ||
                    httpStatus == 422 ->
                    CareHistoryErrorKind
                        .VALIDATION

                failure.code ==
                    "NETWORK_ERROR" ->
                    CareHistoryErrorKind
                        .NETWORK

                httpStatus != null &&
                    httpStatus >= 500 ->
                    CareHistoryErrorKind
                        .SERVER

                else ->
                    CareHistoryErrorKind
                        .UNKNOWN
            }

        val message =
            when (kind) {
                CareHistoryErrorKind.AUTH_EXPIRED ->
                    "로그인이 만료됐어요. 다시 로그인해주세요."

                CareHistoryErrorKind.NOT_FOUND ->
                    "케어 이력을 확인할 수 없어요."

                CareHistoryErrorKind.CONFLICT ->
                    "같은 요청 키로 다른 내용이 처리됐어요. 새로고침 후 다시 등록해주세요."

                CareHistoryErrorKind.VALIDATION ->
                    "등록 날짜와 케어 유형을 확인해주세요."

                CareHistoryErrorKind.NETWORK ->
                    "인터넷 연결을 확인한 뒤 다시 시도해주세요."

                CareHistoryErrorKind.SERVER ->
                    "잠시 처리에 문제가 생겼어요. 잠시 후 다시 시도해주세요."

                CareHistoryErrorKind.UNKNOWN ->
                    "케어 이력을 처리하는 중 문제가 생겼어요."
            }

        _state.value =
            _state.value.copy(
                loadingSubscriptions = false,
                loadingHistory = false,
                isCreating = false,
                errorKind = kind,
                errorMessage = message,
                authExpired =
                    kind ==
                        CareHistoryErrorKind
                            .AUTH_EXPIRED,
            )
    }

    private fun setLocalValidationError(
        message: String,
    ) {
        _state.value =
            _state.value.copy(
                isCreating = false,
                errorKind =
                    CareHistoryErrorKind
                        .VALIDATION,
                errorMessage = message,
            )
    }

    private fun setLocalNotFound() {
        _state.value =
            _state.value.copy(
                errorKind =
                    CareHistoryErrorKind
                        .NOT_FOUND,
                errorMessage =
                    "케어 이력을 확인할 수 없어요.",
            )
    }

    private fun isEligibleSubscription(
        subscription:
            SubscriptionSummaryDto,
    ): Boolean =
        subscription.statusCode ==
            "ACTIVE" &&
            subscription.product.modelCode ==
                P0_SUPPORTED_MODEL_CODE

    private fun parseDate(
        value: String,
    ): LocalDate? =
        runCatching {
            LocalDate.parse(
                value.trim(),
                DateTimeFormatter
                    .ISO_LOCAL_DATE,
            )
        }.getOrNull()
}