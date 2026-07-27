package com.skn29.watercare

import com.skn29.watercare.domain.InquiryEvent
import com.skn29.watercare.domain.InquiryStateMachine
import com.skn29.watercare.model.InquiryState
import org.junit.Assert.assertEquals
import org.junit.Test

class InquiryStateMachineTest {
    @Test
    fun startInquiryCreatesDraft() {
        assertEquals(InquiryState.DRAFT, InquiryStateMachine.next(null, InquiryEvent.StartInquiry))
    }

    @Test
    fun questionnaireCanConfirmError() {
        assertEquals(
            InquiryState.ERROR_CONFIRMED,
            InquiryStateMachine.next(
                InquiryState.QUESTIONNAIRE_IN_PROGRESS,
                InquiryEvent.ConfirmError
            )
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun invalidVisitRequestIsRejected() {
        InquiryStateMachine.next(InquiryState.RESOLVED, InquiryEvent.RequestVisit)
    }
}
