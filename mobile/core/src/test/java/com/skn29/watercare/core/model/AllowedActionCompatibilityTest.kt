package com.skn29.watercare.core.model

import com.skn29.watercare.core.network.parseRuntimeAllowedAction
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AllowedActionCompatibilityTest {
    private val json = Json

    @Test
    fun codeOnlyAction_isParsedWithoutInventingUiMetadata() {
        val element = json.parseToJsonElement("\"CANCEL_INQUIRY\"")

        val action = parseRuntimeAllowedAction(element)

        requireNotNull(action)
        assertEquals("CANCEL_INQUIRY", action.code)
        assertEquals(null, action.label)
        assertEquals(null, action.operationId)
        assertFalse(action.objectContractAvailable)
    }

    @Test
    fun completeObjectAction_isSafeForMutationButton() {
        val element: JsonElement = json.parseToJsonElement(
            """
            {
              "code": "CANCEL_INQUIRY",
              "label": "문의 취소",
              "operation_id": "cancelInquiry",
              "style": "DESTRUCTIVE",
              "requires_confirmation": true,
              "confirmation_message": "문의를 취소하시겠습니까?"
            }
            """.trimIndent()
        )

        val action = parseRuntimeAllowedAction(element)

        requireNotNull(action)
        assertEquals("CANCEL_INQUIRY", action.code)
        assertEquals("문의 취소", action.label)
        assertTrue(action.requiresConfirmation)
        assertTrue(action.objectContractAvailable)
    }

    @Test
    fun incompleteObjectAction_isNotSafeForMutationButton() {
        val element = json.parseToJsonElement(
            """{"code":"CANCEL_INQUIRY","label":"문의 취소"}"""
        )

        val action = parseRuntimeAllowedAction(element)

        requireNotNull(action)
        assertFalse(action.objectContractAvailable)
    }
}
