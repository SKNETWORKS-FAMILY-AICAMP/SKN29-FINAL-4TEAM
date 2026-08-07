package com.skn29.watercare.core.repository

import java.util.UUID

data class CancelOperationIdentity(
    val inquiryId: String,
    val stateVersion: Int,
    val reasonCode: String,
    val reasonDetail: String?,
)

class CancelIdempotencyKeyStore(
    private val createKey: () -> String = {
        UUID.randomUUID().toString()
    },
) {
    private val lock = Any()
    private val pending = mutableMapOf<CancelOperationIdentity, String>()

    fun keyFor(operation: CancelOperationIdentity): String =
        synchronized(lock) {
            pending.getOrPut(operation, createKey)
        }

    fun complete(operation: CancelOperationIdentity) {
        synchronized(lock) {
            pending.remove(operation)
        }
    }
}