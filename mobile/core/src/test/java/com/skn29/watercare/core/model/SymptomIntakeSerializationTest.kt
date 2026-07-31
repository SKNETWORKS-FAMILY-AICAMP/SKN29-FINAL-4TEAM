package com.skn29.watercare.core.model

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SymptomIntakeSerializationTest {
    @Test
    fun request_serializesContractFieldNames_withoutInternalEvidenceFields() {
        val encoded = Json.encodeToString(
            SymptomIntakeRequest(
                subscriptionId = "00000000-0000-4000-8000-000000000101",
                symptomCodes = listOf("LOW_FLOW"),
                rawText = "출수량이 줄었습니다.",
                occurrenceCondition = "냉수 출수 시",
                displayText = "E01",
                entryMode = "ADHOC_INQUIRY",
                idempotencyKey = "idem-1",
            )
        )
        assertTrue(encoded.contains("\"subscription_id\""))
        assertTrue(encoded.contains("\"symptom_codes\""))
        assertTrue(encoded.contains("\"idempotency_key\""))
        assertFalse(encoded.contains("chunk_id"))
        assertFalse(encoded.contains("source_path"))
        assertFalse(encoded.contains("retrieval_text"))
    }
}
