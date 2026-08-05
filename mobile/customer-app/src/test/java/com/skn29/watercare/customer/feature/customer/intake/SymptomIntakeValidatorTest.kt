package com.skn29.watercare.customer.feature.customer.intake

import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.customer.feature.customer.intake.data.SymptomIntakeValidator
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SymptomIntakeValidatorTest {
    @Test
    fun noTopicAndNoRawText_isRejected() {
        assertFalse(SymptomIntakeValidator.validate(emptySet(), "").isValid)
    }

    @Test
    fun selectedTopicWithoutRawText_isRejected() {
        assertFalse(SymptomIntakeValidator.validate(setOf(SymptomTopic.LOW_FLOW), "").isValid)
    }

    @Test
    fun selectedTopicWithRawText_isAccepted() {
        assertTrue(
            SymptomIntakeValidator.validate(
                setOf(SymptomTopic.LOW_FLOW),
                "냉수 출수량이 평소보다 줄었습니다.",
            ).isValid
        )
    }
}
