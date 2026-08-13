package com.skn29.watercare.core.repository

import java.util.UUID

data class ConsultationRequestOperationIdentity(
    val inquiryId: String,
    val stateVersion: Int,
)

class ConsultationRequestIdempotencyKeyStore(
    private val createKey: () -> String = {
        UUID.randomUUID().toString()
    },
) {
    private val lock = Any()
    private val pending =
        mutableMapOf<ConsultationRequestOperationIdentity, String>()

    fun keyFor(
        operation: ConsultationRequestOperationIdentity,
    ): String = synchronized(lock) {
        pending.getOrPut(operation, createKey)
    }

    fun complete(
        operation: ConsultationRequestOperationIdentity,
    ) {
        synchronized(lock) {
            pending.remove(operation)
        }
    }

    fun abandon(
        operation: ConsultationRequestOperationIdentity,
    ) {
        synchronized(lock) {
            pending.remove(operation)
        }
    }
}