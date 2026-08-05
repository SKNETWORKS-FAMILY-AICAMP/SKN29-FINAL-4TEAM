package com.skn29.watercare.customer.feature.customer.intake

import androidx.lifecycle.SavedStateHandle
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

internal object SymptomIntakeSavedStateKeys {
    const val SELECTED_SYMPTOMS = "intake.selectedSymptoms"
    const val RAW_TEXT = "intake.rawText"
    const val OCCURRENCE_CONDITION = "intake.occurrenceCondition"
    const val DISPLAY_TEXT = "intake.displayText"
    const val ENTRY_MODE = "intake.entryMode"
    const val FORCED_SCENARIO = "intake.forcedScenario"
}

class SymptomIntakeViewModel(
    private val subscriptionId: String,
    private val repository: CustomerCareRepository,
    private val savedStateHandle: SavedStateHandle = SavedStateHandle(),
) : ViewModel() {
    private val _state = MutableStateFlow(savedStateHandle.restoreDraft())
    val state: StateFlow<SymptomIntakeUiState> = _state.asStateFlow()

    fun toggleSymptom(topic: SymptomTopic) = updateInput {
        copy(
            selectedSymptoms = if (topic in selectedSymptoms) {
                selectedSymptoms - topic
            } else {
                selectedSymptoms + topic
            },
        )
    }

    fun updateRawText(value: String) = updateInput { copy(rawText = value) }
    fun updateOccurrenceCondition(value: String) =
        updateInput { copy(occurrenceCondition = value) }

    fun updateDisplayText(value: String) = updateInput { copy(displayText = value) }
    fun updateEntryMode(value: EntryMode) = updateInput { copy(entryMode = value) }
    fun updateScenario(value: MockScenario?) = updateInput { copy(forcedScenario = value) }

    fun dismissError() {
        update { clearFailure() }
    }

    fun submit() {
        val snapshot = _state.value
        if (snapshot.isSubmitting) return

        val validation = SymptomIntakeValidator.validate(
            snapshot.selectedSymptoms,
            snapshot.rawText,
        )
        if (!validation.isValid) {
            update {
                copy(
                    rawTextError = validation.rawTextError,
                    globalError = validation.globalError,
                    errorKind = IntakeErrorKind.VALIDATION,
                )
            }
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
                clearFailure().copy(isSubmitting = true)
            }

            when (val result = repository.submitIntake(request)) {
                is ApiResult.Success -> {
                    savedStateHandle.clearDraft()
                    _state.value = _state.value.clearFailure().copy(
                        isSubmitting = false,
                        completed = result.value,
                    )
                }

                is ApiResult.Failure -> update {
                    copy(
                        isSubmitting = false,
                        globalError = result.message,
                        errorKind = result.toIntakeErrorKind(),
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

    fun consumeAuthExpired() {
        if (_state.value.errorKind == IntakeErrorKind.AUTH_EXPIRED) {
            _state.value = _state.value.clearFailure()
        }
    }

    private fun updateInput(
        transform: SymptomIntakeUiState.() -> SymptomIntakeUiState,
    ) {
        update {
            transform().clearFailure()
        }
    }

    private fun update(
        transform: SymptomIntakeUiState.() -> SymptomIntakeUiState,
    ) {
        val updated = _state.value.transform()
        _state.value = updated
        savedStateHandle.persistDraft(updated)
    }

    private fun SymptomIntakeUiState.clearFailure(): SymptomIntakeUiState = copy(
        rawTextError = null,
        globalError = null,
        errorKind = null,
        retryable = false,
        conflictStatus = null,
        conflictStateVersion = null,
        conflictAllowedActions = emptyList(),
    )

    private fun ApiResult.Failure.toIntakeErrorKind(): IntakeErrorKind {
        val status = httpStatus
        return when {
            status == 400 || status == 422 -> IntakeErrorKind.VALIDATION
            status == 401 -> IntakeErrorKind.AUTH_EXPIRED
            status == 403 -> IntakeErrorKind.FORBIDDEN
            status == 404 -> IntakeErrorKind.NOT_FOUND
            status == 409 -> IntakeErrorKind.CONFLICT
            status != null && status >= 500 -> IntakeErrorKind.SERVER
            code == "NETWORK_ERROR" -> IntakeErrorKind.NETWORK
            else -> IntakeErrorKind.UNKNOWN
        }
    }

    private fun SavedStateHandle.restoreDraft(): SymptomIntakeUiState {
        val restoredSymptoms = get<ArrayList<String>>(
            SymptomIntakeSavedStateKeys.SELECTED_SYMPTOMS
        ).orEmpty().mapNotNull { name ->
            runCatching { SymptomTopic.valueOf(name) }.getOrNull()
        }.toSet()

        val restoredEntryMode = get<String>(
            SymptomIntakeSavedStateKeys.ENTRY_MODE
        )?.let { name ->
            runCatching { EntryMode.valueOf(name) }.getOrNull()
        } ?: EntryMode.ADHOC_INQUIRY

        val restoredScenario = get<String>(
            SymptomIntakeSavedStateKeys.FORCED_SCENARIO
        )?.let { name ->
            runCatching { MockScenario.valueOf(name) }.getOrNull()
        }

        return SymptomIntakeUiState(
            selectedSymptoms = restoredSymptoms,
            rawText = get<String>(SymptomIntakeSavedStateKeys.RAW_TEXT).orEmpty(),
            occurrenceCondition = get<String>(
                SymptomIntakeSavedStateKeys.OCCURRENCE_CONDITION
            ).orEmpty(),
            displayText = get<String>(
                SymptomIntakeSavedStateKeys.DISPLAY_TEXT
            ).orEmpty(),
            entryMode = restoredEntryMode,
            forcedScenario = restoredScenario,
        )
    }

    private fun SavedStateHandle.persistDraft(state: SymptomIntakeUiState) {
        set(
            SymptomIntakeSavedStateKeys.SELECTED_SYMPTOMS,
            ArrayList(state.selectedSymptoms.map(SymptomTopic::name).sorted()),
        )
        set(SymptomIntakeSavedStateKeys.RAW_TEXT, state.rawText)
        set(
            SymptomIntakeSavedStateKeys.OCCURRENCE_CONDITION,
            state.occurrenceCondition,
        )
        set(SymptomIntakeSavedStateKeys.DISPLAY_TEXT, state.displayText)
        set(SymptomIntakeSavedStateKeys.ENTRY_MODE, state.entryMode.name)

        val scenario = state.forcedScenario
        if (scenario == null) {
            remove<String>(SymptomIntakeSavedStateKeys.FORCED_SCENARIO)
        } else {
            set(SymptomIntakeSavedStateKeys.FORCED_SCENARIO, scenario.name)
        }
    }

    private fun SavedStateHandle.clearDraft() {
        remove<ArrayList<String>>(SymptomIntakeSavedStateKeys.SELECTED_SYMPTOMS)
        remove<String>(SymptomIntakeSavedStateKeys.RAW_TEXT)
        remove<String>(SymptomIntakeSavedStateKeys.OCCURRENCE_CONDITION)
        remove<String>(SymptomIntakeSavedStateKeys.DISPLAY_TEXT)
        remove<String>(SymptomIntakeSavedStateKeys.ENTRY_MODE)
        remove<String>(SymptomIntakeSavedStateKeys.FORCED_SCENARIO)
    }
}
