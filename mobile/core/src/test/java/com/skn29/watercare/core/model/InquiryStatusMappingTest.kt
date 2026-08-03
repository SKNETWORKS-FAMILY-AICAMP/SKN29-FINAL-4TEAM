package com.skn29.watercare.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class InquiryStatusMappingTest {
    @Test
    fun canonicalServerStatus_mapsToUiDisplayState() {
        val status = ServerInquiryStatus.parse("VISIT_SCHEDULING")
        assertEquals(KnownInquiryStatus.VISIT_SCHEDULING, status.known)
        assertEquals(InquiryDisplayState.VISIT, InquiryStatusMapper.displayState(status))
    }

    @Test
    fun unknownServerStatus_preservesRawCode() {
        val status = ServerInquiryStatus.parse("BACKEND_NEW_STATE")
        assertNull(status.known)
        assertEquals("BACKEND_NEW_STATE", status.rawCode)
        assertEquals(InquiryDisplayState.UNKNOWN, InquiryStatusMapper.displayState(status))
    }

    @Test
    fun trackingLikeValue_isNotCanonicalVisitStatus() {
        val status = ServerVisitStatus.parse("EN_ROUTE")
        assertNull(status.known)
    }
}
