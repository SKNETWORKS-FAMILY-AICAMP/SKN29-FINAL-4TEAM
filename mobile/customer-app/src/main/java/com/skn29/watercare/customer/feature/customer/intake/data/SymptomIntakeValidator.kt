package com.skn29.watercare.customer.feature.customer.intake.data

import com.skn29.watercare.core.model.SymptomTopic

data class IntakeValidationResult(
    val rawTextError: String? = null,
    val globalError: String? = null,
) {
    val isValid: Boolean get() = rawTextError == null && globalError == null
}

object SymptomIntakeValidator {
    fun validate(selected: Set<SymptomTopic>, rawText: String): IntakeValidationResult {
        if (rawText.isBlank()) {
            return IntakeValidationResult(
                rawTextError = "증상 설명은 필수입니다.",
                globalError = "증상을 자세히 입력해 주세요.",
            )
        }
        if (rawText.length > 5000) {
            return IntakeValidationResult(rawTextError = "증상 설명은 5,000자 이하여야 합니다.")
        }
        return IntakeValidationResult()
    }
}
