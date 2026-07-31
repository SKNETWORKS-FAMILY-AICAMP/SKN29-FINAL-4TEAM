package com.skn29.watercare.customer.feature.customer.intake.data

import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomIntakeRequest
import com.skn29.watercare.core.model.SymptomTopic
import java.util.UUID

object SymptomIntakeMapper {
    fun toRequest(
        subscriptionId: String,
        selected: Set<SymptomTopic>,
        rawText: String,
        occurrenceCondition: String,
        displayText: String,
        entryMode: EntryMode,
        scenario: MockScenario?,
    ) = SymptomIntakeRequest(
        subscriptionId = subscriptionId,
        symptomCodes = selected.map { it.code }.sorted(),
        rawText = rawText.trim(),
        occurrenceCondition = occurrenceCondition.trim().ifBlank { null },
        displayText = displayText.trim().ifBlank { null },
        entryMode = entryMode.name,
        idempotencyKey = UUID.randomUUID().toString(),
        mockScenario = scenario?.name,
    )
}
