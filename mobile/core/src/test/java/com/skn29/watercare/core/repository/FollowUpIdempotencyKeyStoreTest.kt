package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.FollowUpAnswer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class FollowUpIdempotencyKeyStoreTest {
    @Test
    fun sameOperation_reusesKey_untilSuccess() {
        var sequence = 0
        val store = FollowUpIdempotencyKeyStore { "key-${++sequence}" }
        val operation = operation("첫 답변")
        val first = store.keyFor(operation)
        assertEquals(first, store.keyFor(operation))
        store.complete(operation)
        assertNotEquals(first, store.keyFor(operation))
    }

    @Test
    fun changedAnswer_isNewUserIntentAndGetsNewKey() {
        var sequence = 0
        val store = FollowUpIdempotencyKeyStore { "key-${++sequence}" }
        assertNotEquals(
            store.keyFor(operation("첫 답변")),
            store.keyFor(operation("수정한 답변")),
        )
    }

    @Test
    fun duplicateConflict_abandonPreventsSameKeyReuse() {
        var sequence = 0
        val store = FollowUpIdempotencyKeyStore { "key-${++sequence}" }
        val operation = operation("답변")
        val first = store.keyFor(operation)
        store.abandon(operation)
        assertNotEquals(first, store.keyFor(operation))
    }

    private fun operation(text: String) = FollowUpOperationIdentity(
        inquiryId = "00000000-0000-4000-8000-000000000301",
        stateVersion = 2,
        answers = listOf(
            FollowUpAnswer(
                questionId = "00000000-0000-4000-8000-000000000401",
                answerText = text,
            )
        ),
    )
}
