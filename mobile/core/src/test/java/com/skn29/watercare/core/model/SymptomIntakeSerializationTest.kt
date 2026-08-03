package com.skn29.watercare.core.model

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SymptomIntakeSerializationTest {
    @Test
    fun createInquiryRequest_serializesOnlyConfirmedBackendFields() {
        val encoded = Json.encodeToString(
            CreateInquiryRequest(
                subscriptionId = "20000000-0000-4000-8000-000000000001",
                channelCode = "MOBILE",
                rawText = "출수량이 줄었습니다.",
                representativeSymptomCode = "LOW_FLOW",
            )
        )
        assertTrue(encoded.contains("\"subscription_id\""))
        assertTrue(encoded.contains("\"channel_code\":\"MOBILE\""))
        assertTrue(encoded.contains("\"raw_text\""))
        assertTrue(encoded.contains("\"representative_symptom_code\""))
        assertFalse(encoded.contains("idempotency_key"))
        assertFalse(encoded.contains("chunk_id"))
        assertFalse(encoded.contains("source_path"))
        assertFalse(encoded.contains("retrieval_text"))
    }
}
