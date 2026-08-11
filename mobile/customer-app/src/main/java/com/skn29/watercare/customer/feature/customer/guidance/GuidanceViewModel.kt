package com.skn29.watercare.customer.feature.customer.guidance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.GuidanceMapper
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.InquiryRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class GuidanceViewModel(
    private val inquiryId: String,
    private val scenario: MockScenario,
    private val repository: CustomerCareRepository,
    private val inquiryRepository: InquiryRepository? = null,
) : ViewModel() {
    private val _state = MutableStateFlow<GuidanceUiState>(GuidanceUiState.Loading)
    val state: StateFlow<GuidanceUiState> = _state.asStateFlow()

    private val _cancelState =
        MutableStateFlow<CancelInquiryUiState>(CancelInquiryUiState.Idle)
    val cancelState: StateFlow<CancelInquiryUiState> =
        _cancelState.asStateFlow()

    private var lastCancelReasonCode: String = "CUSTOMER_REQUEST"
    private var lastCancelReasonDetail: String? = null

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = GuidanceUiState.Loading
            _state.value = when (
                val result = repository.getGuidance(inquiryId, scenario)
            ) {
                is ApiResult.Success -> {
                    val mapped = GuidanceMapper.map(result.value)
                    if (mapped.evidence.isEmpty()) {
                        GuidanceUiState.NoEvidence(mapped)
                    } else {
                        GuidanceUiState.Content(mapped)
                    }
                }

                is ApiResult.Failure -> when {
                    result.code.startsWith("AI_") ->
                        GuidanceUiState.AiFailure(
                            result.message,
                            result.retryable,
                        )

                    result.code == "NETWORK_ERROR" ->
                        GuidanceUiState.NetworkFailure(
                            result.message,
                            result.retryable,
                        )

                    else ->
                        GuidanceUiState.Error(
                            result.message,
                            result.retryable,
                        )
                }
            }
        }
    }

    fun cancelInquiry(
        stateVersion: Int?,
        reasonCode: String = "CUSTOMER_REQUEST",
        reasonDetail: String? = null,
    ) {
        val remote = inquiryRepository
        if (remote == null) {
            _cancelState.value = CancelInquiryUiState.Error(
                message = "문의 취소 기능을 사용할 수 없습니다.",
                retryable = false,
            )
            return
        }

        if (stateVersion == null || stateVersion < 1) {
            _cancelState.value = CancelInquiryUiState.Error(
                message = "최신 문의 상태 버전을 확인한 뒤 다시 시도해 주세요.",
                retryable = false,
            )
            return
        }

        lastCancelReasonCode = reasonCode
        lastCancelReasonDetail = reasonDetail
        performCancel(
            repository = remote,
            stateVersion = stateVersion,
            reasonCode = reasonCode,
            reasonDetail = reasonDetail,
        )
    }

    fun retryCancelAfterConflict() {
        val current = _cancelState.value
        if (current !is CancelInquiryUiState.Conflict) return

        val latestVersion = current.currentStateVersion
        val canRetry =
            latestVersion != null &&
                current.allowedActions.any {
                    it.normalizedCode ==
                        InquiryActionLabels.CANCEL_INQUIRY
                }

        if (!canRetry) return

        val remote = inquiryRepository ?: return
        performCancel(
            repository = remote,
            stateVersion = latestVersion,
            reasonCode = lastCancelReasonCode,
            reasonDetail = lastCancelReasonDetail,
        )
    }

    private fun performCancel(
        repository: InquiryRepository,
        stateVersion: Int,
        reasonCode: String,
        reasonDetail: String?,
    ) {
        viewModelScope.launch {
            _cancelState.value = CancelInquiryUiState.Cancelling
            _cancelState.value = when (
                val result = repository.cancel(
                    inquiryId = inquiryId,
                    stateVersion = stateVersion,
                    reasonCode = reasonCode,
                    reasonDetail = reasonDetail,
                )
            ) {
                is ApiResult.Success ->
                    CancelInquiryUiState.Success(
                        state = result.value.state,
                        stateVersion = result.value.stateVersion,
                        idempotentReplay = result.value.idempotentReplay,
                    )

                is ApiResult.Failure -> {
                    val conflict = result.conflict
                    if (conflict != null) {
                        CancelInquiryUiState.Conflict(
                            message = result.message,
                            currentStatus = conflict.currentStatus,
                            currentStateVersion =
                                conflict.currentStateVersion,
                            allowedActions = conflict.allowedActions,
                        )
                    } else {
                        CancelInquiryUiState.Error(
                            message = result.message,
                            retryable = result.retryable,
                        )
                    }
                }
            }
        }
    }
}

sealed interface CancelInquiryUiState {
    data object Idle : CancelInquiryUiState
    data object Cancelling : CancelInquiryUiState

    data class Success(
        val state: String,
        val stateVersion: Int,
        val idempotentReplay: Boolean,
    ) : CancelInquiryUiState

    data class Conflict(
        val message: String,
        val currentStatus: String?,
        val currentStateVersion: Int?,
        val allowedActions: List<AllowedAction>,
    ) : CancelInquiryUiState {
        val canRetry: Boolean
            get() =
                currentStateVersion != null &&
                    allowedActions.any {
                        it.normalizedCode ==
                            InquiryActionLabels.CANCEL_INQUIRY
                    }
    }

    data class Error(
        val message: String,
        val retryable: Boolean,
    ) : CancelInquiryUiState
}
