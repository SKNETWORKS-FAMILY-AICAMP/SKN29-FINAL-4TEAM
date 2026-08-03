package com.skn29.watercare.customer.feature.customer.inquirycreated

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.customer.repository.InquiryRepository
import com.skn29.watercare.customer.data.watercare.InquirySessionStore
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class InquiryCreatedViewModel(
    private val inquiryId: String,
    private val repository: InquiryRepository,
    private val sessionStore: InquirySessionStore,
) : ViewModel() {
    private val _state = MutableStateFlow(InquiryCreatedUiState())
    val state: StateFlow<InquiryCreatedUiState> = _state.asStateFlow()

    private var pendingCancelIdempotencyKey: String? = null

    init {
        viewModelScope.launch {
            sessionStore.current.collect { snapshot ->
                val matching = snapshot?.takeIf { it.inquiryId == inquiryId }
                _state.value = _state.value.copy(
                    loading = false,
                    inquiry = matching,
                    correlationId = matching?.correlationId ?: _state.value.correlationId,
                    error = if (matching == null) {
                        "현재 앱 세션에서 문의 정보를 찾을 수 없습니다. 홈에서 다시 접수해 주세요."
                    } else {
                        _state.value.error
                    },
                )
            }
        }
    }

    fun cancel() {
        val inquiry = _state.value.inquiry ?: return
        if (_state.value.cancelling) return
        val cancelAction = inquiry.allowedActions.firstOrNull { it.code == "CANCEL_INQUIRY" }
        if (cancelAction == null) {
            _state.value = _state.value.copy(
                error = "Backend가 문의 취소를 허용하지 않는 현재 상태입니다.",
                retryable = false,
            )
            return
        }
        if (!cancelAction.objectContractAvailable) {
            _state.value = _state.value.copy(
                error = "allowed_actions가 코드 문자열로만 전달되어 안전을 위해 취소 요청을 비활성화했습니다.",
                retryable = false,
            )
            return
        }

        val idempotencyKey = pendingCancelIdempotencyKey ?: UUID.randomUUID().toString()
        pendingCancelIdempotencyKey = idempotencyKey
        viewModelScope.launch {
            _state.value = _state.value.copy(cancelling = true, error = null, retryable = false)
            when (val result = repository.cancel(
                inquiryId = inquiry.inquiryId,
                stateVersion = inquiry.stateVersion,
                reasonCode = "CUSTOMER_REQUEST",
                reasonDetail = null,
                idempotencyKey = idempotencyKey,
            )) {
                is ApiResult.Success -> {
                    pendingCancelIdempotencyKey = null
                    _state.value = _state.value.copy(
                        cancelling = false,
                        correlationId = result.metadata?.correlationId ?: _state.value.correlationId,
                    )
                }
                is ApiResult.Failure -> {
                    _state.value = _state.value.copy(
                        cancelling = false,
                        error = result.message,
                        retryable = result.retryable,
                        correlationId = result.correlationId ?: _state.value.correlationId,
                    )
                }
            }
        }
    }

    fun dismissError() {
        _state.value = _state.value.copy(error = null, retryable = false)
    }
}
