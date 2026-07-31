package com.skn29.watercare.customer.feature.customer.intake

import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic

data class SymptomIntakeUiState(
    val selectedSymptoms: Set<SymptomTopic> = emptySet(),
    val rawText: String = "",
    val occurrenceCondition: String = "",
    val displayText: String = "",
    val entryMode: EntryMode = EntryMode.ADHOC_INQUIRY,
    val forcedScenario: MockScenario? = null,
    val isSubmitting: Boolean = false,
    val rawTextError: String? = null,
    val globalError: String? = null,
    val retryable: Boolean = false,
    val conflictStatus: String? = null,
    val conflictStateVersion: Int? = null,
    val conflictAllowedActions: List<String> = emptyList(),
    val completed: IntakeSubmission? = null,
)
