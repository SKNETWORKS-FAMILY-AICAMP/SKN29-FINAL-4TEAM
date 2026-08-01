package com.skn29.watercare.core.model

import org.junit.Assert.assertEquals
import org.junit.Test

class KoreanDateTimeFormatterTest {
    @Test
    fun offsetDateTime_isFormattedWithoutAddingNineHoursAgain() {
        assertEquals("2026.07.31 10:30", KoreanDateTimeFormatter.format("2026-07-31T10:30:00+09:00"))
    }

    @Test
    fun invalidValue_isReturnedSafely() {
        assertEquals("not-a-date", KoreanDateTimeFormatter.format("not-a-date"))
    }
}
