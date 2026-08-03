package com.skn29.watercare.customer.feature.customer.intake

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.customer.repository.InquiryRepository
import com.skn29.watercare.customer.feature.customer.intake.data.SymptomIntakeMapper
import com.skn29.watercare.customer.feature.customer.intake.data.SymptomIntakeValidator
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private object IntakeDraftCache {
    var state: SymptomIntakeUiState = SymptomIntakeUiState()
}

class SymptomIntakeViewModel(
    private val subscriptionId: String,
    private val repository: InquiryRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(IntakeDraftCache.state.copy(completed = null))
    val state: StateFlow<SymptomIntakeUiState> = _state.asStateFlow()

    fun toggleSymptom(topic: SymptomTopic) = updateRequestInput {
        copy(
            selectedSymptoms = if (topic in selectedSymptoms) selectedSymptoms - topic else selectedSymptoms + topic,
            rawTextError = null,
            globalError = null,
        )
    }

    fun updateRawText(value: String) = updateRequestInput {
        copy(rawText = value, rawTextError = null, globalError = null)
    }

    fun updateOccurrenceCondition(value: String) = updateRequestInput {
        copy(occurrenceCondition = value, globalError = null)
    }

    fun updateDisplayText(value: String) = updateRequestInput {
        copy(displayText = value, globalError = null)
    }

    fun updateEntryMode(value: EntryMode) = updateRequestInput {
        copy(entryMode = value, globalError = null)
    }

    fun updateScenario(value: MockScenario?) = update {
        copy(forcedScenario = value)
    }

    fun dismissError() = update {
        copy(
            globalError = null,
            retryable = false,
            authExpired = false,
            conflictStatus = null,
            conflictStateVersion = null,
            conflictAllowedActions = emptyList(),
        )
    }

    fun submit() {
        val snapshot = _state.value
        if (snapshot.isSubmitting) return
        if (subscriptionId == "UNCONFIGURED" || subscriptionId.isBlank()) {
            update {
                copy(
                    globalError = "실제 문의 생성에는 활성 구독 Public UUID가 필요합니다. mobile/local.properties의 DEMO_SUBSCRIPTION_ID를 설정해 주세요.",
                    retryable = false,
                )
            }
            return
        }
        val validation = SymptomIntakeValidator.validate(snapshot.selectedSymptoms, snapshot.rawText)
        if (!validation.isValid) {
            update { copy(rawTextError = validation.rawTextError, globalError = validation.globalError) }
            return
        }

        val request = SymptomIntakeMapper.toCreateInquiryRequest(
            subscriptionId = subscriptionId,
            selected = snapshot.selectedSymptoms,
            rawText = snapshot.rawText,
            occurrenceCondition = snapshot.occurrenceCondition,
            displayText = snapshot.displayText,
            entryMode = snapshot.entryMode,
        )
        val idempotencyKey = snapshot.pendingIdempotencyKey ?: UUID.randomUUID().toString()

        viewModelScope.launch {
            update {
                copy(
                    isSubmitting = true,
                    globalError = null,
                    retryable = false,
                    authExpired = false,
                    conflictStatus = null,
                    conflictStateVersion = null,
                    conflictAllowedActions = emptyList(),
                    correlationId = null,
                    pendingIdempotencyKey = idempotencyKey,
                )
            }
            when (val result = repository.create(request, idempotencyKey)) {
                is ApiResult.Success -> {
                    val response = result.value
                    _state.value = _state.value.copy(
                        isSubmitting = false,
                        pendingIdempotencyKey = null,
                        correlationId = result.metadata?.correlationId,
                        completed = IntakeSubmission(
                            inquiryId = response.inquiryId,
                            inquiryCode = response.inquiryCode,
                            statusCode = response.statusCode,
                            stateVersion = response.stateVersion,
                            allowedActionCodes = response.allowedActions.map { it.code },
                            correlationId = result.metadata?.correlationId,
                            idempotentReplay = response.idempotentReplay,
                            guidanceScenario = SymptomIntakeMapper.previewScenario(snapshot.forcedScenario),
                        ),
                    )
                    IntakeDraftCache.state = SymptomIntakeUiState()
                }
                is ApiResult.Failure -> {
                    val authenticationExpired =
                        result.httpStatus == 401 ||
                            result.code == "AUTH_REQUIRED"

                    update {
                        copy(
                            isSubmitting = false,
                            rawTextError =
                                result.fieldErrors["raw_text"]
                                    ?.joinToString(" ")
                                    ?: rawTextError,
                            globalError = result.message,
                            retryable = !authenticationExpired && (
                                result.retryable ||
                                    result.code == "NETWORK_ERROR"
                            ),
                            authExpired = authenticationExpired,
                            conflictStatus = result.conflict?.currentStatus,
                            conflictStateVersion =
                                result.conflict?.currentStateVersion,
                            conflictAllowedActions =
                                result.conflict
                                    ?.allowedActions
                                    ?.map { it.code }
                                    .orEmpty(),
                            correlationId = result.correlationId,
                            // Keep the key so retrying the same payload remains idempotent.
                            pendingIdempotencyKey = idempotencyKey,
                        )
                    }
                }
            }
        }
    }

    fun consumeCompletion() {
        _state.value = _state.value.copy(completed = null)
    }

    fun consumeAuthExpiration() {
        update {
            copy(authExpired = false)
        }
    }

    private fun updateRequestInput(transform: SymptomIntakeUiState.() -> SymptomIntakeUiState) {
        update {
            transform().copy(
                pendingIdempotencyKey = null,
                authExpired = false,
                conflictStatus = null,
                conflictStateVersion = null,
                conflictAllowedActions = emptyList(),
                correlationId = null,
            )
        }
    }

    private fun update(transform: SymptomIntakeUiState.() -> SymptomIntakeUiState) {
        val updated = _state.value.transform()
        _state.value = updated
        if (updated.completed == null) IntakeDraftCache.state = updated.copy(isSubmitting = false)
    }
}
