package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.repository.InquiryRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

internal class InquiryCancelRuntime(
    private val inquiryId: String,
    private val repository: InquiryRepository?,
    private val scope: CoroutineScope,
    private val onAuthExpired: () -> Unit = {},
) {
    private val _state =
        MutableStateFlow<CancelInquiryUiState>(
            CancelInquiryUiState.Idle
        )

    val state: StateFlow<CancelInquiryUiState> =
        _state.asStateFlow()

    private var lastReasonCode: String =
        "CUSTOMER_REQUEST"

    private var lastReasonDetail: String? = null

    fun cancelInquiry(
        stateVersion: Int?,
        reasonCode: String = "CUSTOMER_REQUEST",
        reasonDetail: String? = null,
    ) {
        val remote = repository

        if (remote == null) {
            _state.value =
                CancelInquiryUiState.Error(
                    message =
                        "?? ?? ??? ??? ? ????.",
                    retryable = false,
                )
            return
        }

        if (stateVersion == null || stateVersion < 1) {
            _state.value =
                CancelInquiryUiState.Error(
                    message =
                        "?? ?? ?? ??? ??? ? ?? ??? ???.",
                    retryable = false,
                )
            return
        }

        if (_state.value is CancelInquiryUiState.Cancelling) {
            return
        }

        lastReasonCode = reasonCode
        lastReasonDetail = reasonDetail

        performCancel(
            repository = remote,
            stateVersion = stateVersion,
            reasonCode = reasonCode,
            reasonDetail = reasonDetail,
        )
    }

    fun retryAfterConflict() {
        val current =
            _state.value as?
                CancelInquiryUiState.Conflict
                ?: return

        if (!current.canRetry) {
            return
        }

        val latestVersion =
            current.currentStateVersion
                ?: return

        val remote =
            repository
                ?: return

        performCancel(
            repository = remote,
            stateVersion = latestVersion,
            reasonCode = lastReasonCode,
            reasonDetail = lastReasonDetail,
        )
    }

    private fun performCancel(
        repository: InquiryRepository,
        stateVersion: Int,
        reasonCode: String,
        reasonDetail: String?,
    ) {
        if (_state.value is CancelInquiryUiState.Cancelling) {
            return
        }

        _state.value =
            CancelInquiryUiState.Cancelling

        scope.launch {
            _state.value =
                when (
                    val result =
                        repository.cancel(
                            inquiryId = inquiryId,
                            stateVersion = stateVersion,
                            reasonCode = reasonCode,
                            reasonDetail = reasonDetail,
                        )
                ) {
                    is ApiResult.Success ->
                        CancelInquiryUiState.Success(
                            state =
                                result.value.state,
                            stateVersion =
                                result.value.stateVersion,
                            idempotentReplay =
                                result.value.idempotentReplay,
                        )

                    is ApiResult.Failure -> {
                        if (result.httpStatus == 401) {
                            onAuthExpired()
                        }

                        val conflict =
                            result.conflict

                        if (conflict != null) {
                            CancelInquiryUiState.Conflict(
                                message =
                                    result.message,
                                currentStatus =
                                    conflict.currentStatus,
                                currentStateVersion =
                                    conflict.currentStateVersion,
                                allowedActions =
                                    conflict.allowedActions,
                            )
                        } else {
                            CancelInquiryUiState.Error(
                                message =
                                    result.message,
                                retryable =
                                    result.retryable,
                            )
                        }
                    }
                }
        }
    }
}

internal fun canCancelInquiry(
    statusCode: String?,
    stateVersion: Int?,
    allowedActions:
        List<com.skn29.watercare.core.model.AllowedAction>,
): Boolean =
    statusCode in
        setOf(
            "DRAFT",
            "QUESTIONNAIRE_IN_PROGRESS",
        ) &&
        stateVersion != null &&
        stateVersion >= 1 &&
        allowedActions.any {
            it.normalizedCode ==
                InquiryActionLabels.CANCEL_INQUIRY
        }
