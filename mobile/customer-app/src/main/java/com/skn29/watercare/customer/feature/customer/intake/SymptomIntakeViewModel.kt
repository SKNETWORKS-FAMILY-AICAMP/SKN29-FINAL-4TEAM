package com.skn29.watercare.customer.feature.customer.intake

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.customer.feature.customer.intake.data.SymptomIntakeMapper
import com.skn29.watercare.customer.feature.customer.intake.data.SymptomIntakeValidator
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private object IntakeDraftCache {
    var state: SymptomIntakeUiState = SymptomIntakeUiState()
}

class SymptomIntakeViewModel(
    private val subscriptionId: String,
    private val repository: CustomerCareRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(IntakeDraftCache.state.copy(completed = null))
    val state: StateFlow<SymptomIntakeUiState> = _state.asStateFlow()

    fun toggleSymptom(topic: SymptomTopic) = update {
        copy(
            selectedSymptoms = if (topic in selectedSymptoms) selectedSymptoms - topic else selectedSymptoms + topic,
            rawTextError = null,
            globalError = null,
        )
    }

    fun updateRawText(value: String) = update { copy(rawText = value, rawTextError = null, globalError = null) }
    fun updateOccurrenceCondition(value: String) = update { copy(occurrenceCondition = value) }
    fun updateDisplayText(value: String) = update { copy(displayText = value) }
    fun updateEntryMode(value: EntryMode) = update { copy(entryMode = value) }
    fun updateScenario(value: MockScenario?) = update { copy(forcedScenario = value) }
    fun dismissError() = update {
        copy(
            globalError = null,
            retryable = false,
            conflictStatus = null,
            conflictStateVersion = null,
            conflictAllowedActions = emptyList(),
        )
    }

    fun submit() {
        val snapshot = _state.value
        if (snapshot.isSubmitting) return
        val validation = SymptomIntakeValidator.validate(snapshot.selectedSymptoms, snapshot.rawText)
        if (!validation.isValid) {
            update { copy(rawTextError = validation.rawTextError, globalError = validation.globalError) }
            return
        }
        val request = SymptomIntakeMapper.toRequest(
            subscriptionId = subscriptionId,
            selected = snapshot.selectedSymptoms,
            rawText = snapshot.rawText,
            occurrenceCondition = snapshot.occurrenceCondition,
            displayText = snapshot.displayText,
            entryMode = snapshot.entryMode,
            scenario = snapshot.forcedScenario,
        )
        viewModelScope.launch {
            update {
                copy(
                    isSubmitting = true,
                    globalError = null,
                    retryable = false,
                    conflictStatus = null,
                    conflictStateVersion = null,
                    conflictAllowedActions = emptyList(),
                )
            }
            when (val result = repository.submitIntake(request)) {
                is ApiResult.Success -> {
                    _state.value = _state.value.copy(isSubmitting = false, completed = result.value)
                    IntakeDraftCache.state = _state.value.copy(isSubmitting = false, completed = null)
                }
                is ApiResult.Failure -> update {
                    copy(
                        isSubmitting = false,
                        globalError = result.message,
                        retryable = result.retryable,
                        conflictStatus = result.conflict?.currentStatus,
                        conflictStateVersion = result.conflict?.currentStateVersion,
                        conflictAllowedActions = result.conflict?.allowedActions.orEmpty(),
                    )
                }
            }
        }
    }

    fun consumeCompletion() {
        _state.value = _state.value.copy(completed = null)
    }

    private fun update(transform: SymptomIntakeUiState.() -> SymptomIntakeUiState) {
        val updated = _state.value.transform()
        _state.value = updated
        if (updated.completed == null) IntakeDraftCache.state = updated.copy(isSubmitting = false)
    }
}
