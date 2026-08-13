package com.skn29.watercare.core.repository

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class ConsultationRequestIdempotencyKeyStoreTest {
    @Test
    fun pendingOperation_reusesKeyUntilCompleted() {
        var sequence = 0
        val store = ConsultationRequestIdempotencyKeyStore {
            "consultation-key-${++sequence}"
        }
        val operation = ConsultationRequestOperationIdentity(
            inquiryId = "00000000-0000-4000-8000-000000000301",
            stateVersion = 3,
        )

        val first = store.keyFor(operation)
        val retry = store.keyFor(operation)
        store.complete(operation)
        val nextIntent = store.keyFor(operation)

        assertEquals(first, retry)
        assertNotEquals(first, nextIntent)
    }

    @Test
    fun changedStateVersion_usesNewKey() {
        var sequence = 0
        val store = ConsultationRequestIdempotencyKeyStore {
            "consultation-key-${++sequence}"
        }

        val stale = store.keyFor(
            ConsultationRequestOperationIdentity("inquiry-1", 3)
        )
        val refreshed = store.keyFor(
            ConsultationRequestOperationIdentity("inquiry-1", 4)
        )

        assertNotEquals(stale, refreshed)
    }
}
