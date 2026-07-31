package com.skn29.watercare.core.model

import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException

/**
 * Formats the offset supplied by the API without adding another nine hours.
 * Invalid values are returned unchanged so an unexpected server value never crashes the UI.
 */
object KoreanDateTimeFormatter {
    private val displayFormatter = DateTimeFormatter.ofPattern("yyyy.MM.dd HH:mm")

    fun format(value: String): String = try {
        OffsetDateTime.parse(value).format(displayFormatter)
    } catch (_: DateTimeParseException) {
        value
    }
}
