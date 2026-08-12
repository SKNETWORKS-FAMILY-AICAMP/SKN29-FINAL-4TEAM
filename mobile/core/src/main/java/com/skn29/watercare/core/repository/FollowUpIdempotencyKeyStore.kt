package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.FollowUpAnswer
import java.util.UUID

data class FollowUpOperationIdentity(
    val inquiryId: String,
    val stateVersion: Int,
    val answers: List<FollowUpAnswer>,
)

class FollowUpIdempotencyKeyStore(
    private val createKey: () -> String = { UUID.randomUUID().toString() },
) {
    private val lock = Any()
    private val pending = mutableMapOf<FollowUpOperationIdentity, String>()

    fun keyFor(operation: FollowUpOperationIdentity): String =
        synchronized(lock) { pending.getOrPut(operation, createKey) }

    fun complete(operation: FollowUpOperationIdentity) {
        synchronized(lock) { pending.remove(operation) }
    }

    fun abandon(operation: FollowUpOperationIdentity) {
        synchronized(lock) { pending.remove(operation) }
    }
}
