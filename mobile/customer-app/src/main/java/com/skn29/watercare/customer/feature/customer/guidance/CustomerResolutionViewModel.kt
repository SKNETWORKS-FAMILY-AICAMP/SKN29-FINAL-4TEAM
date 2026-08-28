package com.skn29.watercare.customer.feature.customer.guidance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.ResolutionTransitionResponseDto
import com.skn29.watercare.core.repository.CustomerInquiryRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface CustomerResolutionUiState {
    data object Idle : CustomerResolutionUiState
    data class Submitting(
        val actionCode: String,
    ) : CustomerResolutionUiState
    data class Success(
        val result: ResolutionTransitionResponseDto,
        val actionCode: String,
    ) : CustomerResolutionUiState
    data class Error(
        val message: String,
        val retryable: Boolean,
        val actionCode: String?,
    ) : CustomerResolutionUiState
}

class CustomerResolutionViewModel(
    private val inquiryId: String,
    private val repository: CustomerInquiryRepository,
) : ViewModel() {
    private val _state =
        MutableStateFlow<CustomerResolutionUiState>(
            CustomerResolutionUiState.Idle
        )
    val state: StateFlow<CustomerResolutionUiState> =
        _state.asStateFlow()

    private val _workflowSnapshot =
        MutableStateFlow<CustomerWorkflowUiSnapshot?>(null)
    val workflowSnapshot:
        StateFlow<CustomerWorkflowUiSnapshot?> =
        _workflowSnapshot.asStateFlow()

    private val _authExpired = MutableStateFlow(false)
    val authExpired: StateFlow<Boolean> =
        _authExpired.asStateFlow()

    private var lastActionCode: String? = null

    fun consumeAuthExpired() {
        _authExpired.value = false
    }

    fun markResolved() =
        execute(
            InquiryActionLabels
                .SUBMIT_RESOLUTION_FEEDBACK
        )

    fun reportUnresolved() =
        execute(
            InquiryActionLabels
                .CUSTOMER_REPORTED_UNRESOLVED
        )

    fun retryLastAction() {
        lastActionCode?.let(::execute)
    }

    private fun execute(
        actionCode: String,
    ) {
        if (
            _state.value is
                CustomerResolutionUiState.Submitting
        ) return

        lastActionCode = actionCode
        _state.value =
            CustomerResolutionUiState.Submitting(
                actionCode
            )

        viewModelScope.launch {
            when (
                val snapshot =
                    repository.snapshot(inquiryId)
            ) {
                is ApiResult.Failure ->
                    applyFailure(
                        snapshot,
                        actionCode,
                    )

                is ApiResult.Success -> {
                    val latest = snapshot.value
                    _workflowSnapshot.value =
                        latest.toWorkflowUiSnapshot()

                    val allowed =
                        latest.allowedActions.any {
                            it.normalizedCode ==
                                actionCode
                        }

                    if (!allowed) {
                        _state.value =
                            CustomerResolutionUiState
                                .Error(
                                    "현재 문의 상태에서는 이 작업을 진행할 수 없어요.",
                                    false,
                                    actionCode,
                                )
                        return@launch
                    }

                    val result =
                        if (
                            actionCode ==
                            InquiryActionLabels
                                .SUBMIT_RESOLUTION_FEEDBACK
                        ) {
                            repository
                                .submitResolutionFeedback(
                                    inquiryId,
                                    latest.stateVersion,
                                )
                        } else {
                            repository
                                .reportUnresolved(
                                    inquiryId,
                                    latest.stateVersion,
                                    "STILL_UNRESOLVED",
                                )
                        }

                    when (result) {
                        is ApiResult.Success -> {
                            _workflowSnapshot.value =
                                result.value
                                    .toWorkflowUiSnapshot()

                            _state.value =
                                CustomerResolutionUiState
                                    .Success(
                                        result.value,
                                        actionCode,
                                    )
                        }

                        is ApiResult.Failure ->
                            applyFailure(
                                result,
                                actionCode,
                            )
                    }
                }
            }
        }
    }

    private suspend fun applyFailure(
        failure: ApiResult.Failure,
        actionCode: String,
    ) {
        if (failure.httpStatus == 401) {
            _authExpired.value = true
        }

        if (failure.httpStatus == 409) {
            when (
                val refreshed =
                    repository.snapshot(inquiryId)
            ) {
                is ApiResult.Success ->
                    _workflowSnapshot.value =
                        refreshed.value
                            .toWorkflowUiSnapshot()

                is ApiResult.Failure -> Unit
            }
        }

        _state.value =
            CustomerResolutionUiState.Error(
                message =
                    when {
                        failure.httpStatus == 409 ->
                            "문의 상태가 다른 작업으로 변경됐어요. 최신 상태를 다시 확인했습니다."

                        failure.httpStatus == 422 ->
                            "처리 요청 내용이 올바르지 않아요. 최신 문의 상태를 확인한 뒤 다시 시도해주세요."

                        failure.code ==
                            "NETWORK_ERROR" ->
                            "인터넷 연결을 확인한 뒤 다시 시도해주세요."

                        else ->
                            "처리 결과를 저장하지 못했어요. 잠시 후 다시 시도해주세요."
                    },
                retryable =
                    failure.retryable ||
                        failure.httpStatus == 409,
                actionCode = actionCode,
            )
    }
}
