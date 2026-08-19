package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.InquiryActionLabels
import org.junit.Assert.assertFalse
import org.junit.Test

class CancelInquiryUiStateTest {
    @Test
    fun conflictAiGuidanceWithInjectedCancelAction_doesNotRetry() {
        val conflict =
            CancelInquiryUiState.Conflict(
                message = "state changed",
                currentStatus = "AI_GUIDANCE",
                currentStateVersion = 3,
                allowedActions =
                    listOf(
                        AllowedAction(
                            code =
                                InquiryActionLabels
                                    .CANCEL_INQUIRY,
                        )
                    ),
            )

        assertFalse(conflict.canRetry)
    }
}
