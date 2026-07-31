package com.skn29.watercare.core.model

import org.junit.Assert.assertEquals
import org.junit.Test

class InquiryLabelsTest {
    @Test fun mapsKnownAndUnknownStatusSafely() {
        assertEquals("상담 필요", InquiryLabels.status("CONSULTATION_REQUIRED"))
        assertEquals("확인 중 (NEW_STATE)", InquiryLabels.status("NEW_STATE"))
    }
}
