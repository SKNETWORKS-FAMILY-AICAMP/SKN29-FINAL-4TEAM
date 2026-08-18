package com.skn29.watercare.core.repository

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class CareHistoryIdempotencyKeyStoreTest {
    @Test
    fun sameOperation_reusesPendingKey() {
        var sequence = 0
        val store =
            CareHistoryIdempotencyKeyStore {
                sequence += 1
                "key-$sequence"
            }
        val operation =
            CareHistoryOperationIdentity(
                subscriptionId = "sub",
                careTypeCode =
                    "FILTER_REPLACEMENT",
                performedOn = "2026-08-18",
            )

        val first = store.keyFor(operation)
        val second = store.keyFor(operation)

        assertEquals(first, second)
    }

    @Test
    fun differentPayload_getsDifferentKey() {
        var sequence = 0
        val store =
            CareHistoryIdempotencyKeyStore {
                sequence += 1
                "key-$sequence"
            }

        val first =
            store.keyFor(
                CareHistoryOperationIdentity(
                    subscriptionId = "sub",
                    careTypeCode =
                        "FILTER_REPLACEMENT",
                    performedOn =
                        "2026-08-18",
                )
            )
        val second =
            store.keyFor(
                CareHistoryOperationIdentity(
                    subscriptionId = "sub",
                    careTypeCode = "CLEANING",
                    performedOn =
                        "2026-08-18",
                )
            )

        assertNotEquals(first, second)
    }

    @Test
    fun complete_releasesKeyForNextOperation() {
        var sequence = 0
        val store =
            CareHistoryIdempotencyKeyStore {
                sequence += 1
                "key-$sequence"
            }
        val operation =
            CareHistoryOperationIdentity(
                subscriptionId = "sub",
                careTypeCode = "CLEANING",
                performedOn = "2026-08-18",
            )

        val first = store.keyFor(operation)
        store.complete(operation)
        val next = store.keyFor(operation)

        assertNotEquals(first, next)
    }
}