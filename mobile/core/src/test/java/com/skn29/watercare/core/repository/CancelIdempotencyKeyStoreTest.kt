package com.skn29.watercare.core.repository

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class CancelIdempotencyKeyStoreTest {

    @Test
    fun samePendingCancelOperationReusesSameKey() {
        var sequence = 0
        val store = CancelIdempotencyKeyStore {
            "key-${++sequence}"
        }
        val operation = CancelOperationIdentity(
            inquiryId = "00000000-0000-4000-8000-000000000301",
            stateVersion = 3,
            reasonCode = "CUSTOMER_REQUEST",
            reasonDetail = "사용자 취소",
        )

        val first = store.keyFor(operation)
        val retry = store.keyFor(operation)

        assertEquals(first, retry)
        assertEquals("key-1", retry)
    }

    @Test
    fun changedOperationGetsDifferentKey() {
        var sequence = 0
        val store = CancelIdempotencyKeyStore {
            "key-${++sequence}"
        }

        val first = store.keyFor(
            CancelOperationIdentity(
                inquiryId = "00000000-0000-4000-8000-000000000301",
                stateVersion = 3,
                reasonCode = "CUSTOMER_REQUEST",
                reasonDetail = null,
            )
        )
        val changedState = store.keyFor(
            CancelOperationIdentity(
                inquiryId = "00000000-0000-4000-8000-000000000301",
                stateVersion = 4,
                reasonCode = "CUSTOMER_REQUEST",
                reasonDetail = null,
            )
        )

        assertNotEquals(first, changedState)
    }

    @Test
    fun successfulCompletionAllowsNewOperationKey() {
        var sequence = 0
        val store = CancelIdempotencyKeyStore {
            "key-${++sequence}"
        }
        val operation = CancelOperationIdentity(
            inquiryId = "00000000-0000-4000-8000-000000000301",
            stateVersion = 3,
            reasonCode = "CUSTOMER_REQUEST",
            reasonDetail = null,
        )

        val first = store.keyFor(operation)
        store.complete(operation)
        val afterCompletion = store.keyFor(operation)

        assertNotEquals(first, afterCompletion)
        assertEquals("key-2", afterCompletion)
    }
}
