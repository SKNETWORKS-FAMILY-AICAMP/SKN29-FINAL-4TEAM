package com.skn29.watercare.customer.feature.customer.intake

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.ResponseMetadata
import com.skn29.watercare.core.model.toCodeOnlyRuntimeAction
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.customer.repository.InquiryRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SymptomIntakeViewModelTest {
    @get:Rule val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun failedSubmission_keepsInputAndAllowsRetry() = runTest(mainDispatcherRule.dispatcher) {
        val repository = RecordingInquiryRepository(
            createResult = ApiResult.Failure("NETWORK_ERROR", "network", retryable = true)
        )
        val viewModel = SymptomIntakeViewModel("subscription", repository)
        viewModel.updateRawText("입력 유지 테스트")
        viewModel.submit()
        advanceUntilIdle()

        assertEquals("입력 유지 테스트", viewModel.state.value.rawText)
        assertFalse(viewModel.state.value.isSubmitting)
        assertNotNull(viewModel.state.value.globalError)
        assertNotNull(viewModel.state.value.pendingIdempotencyKey)
    }

    @Test
    fun retryingSamePayload_reusesIdempotencyKey() = runTest(mainDispatcherRule.dispatcher) {
        val repository = RecordingInquiryRepository(
            createResult = ApiResult.Failure("NETWORK_ERROR", "network", retryable = true)
        )
        val viewModel = SymptomIntakeViewModel("subscription", repository)
        viewModel.updateRawText("동일 요청")
        viewModel.submit()
        advanceUntilIdle()
        viewModel.submit()
        advanceUntilIdle()

        assertEquals(2, repository.idempotencyKeys.size)
        assertEquals(repository.idempotencyKeys[0], repository.idempotencyKeys[1])
    }

    @Test
    fun editingPayload_createsNewIdempotencyKey() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = RecordingInquiryRepository(
                createResult = ApiResult.Failure(
                    code = "NETWORK_ERROR",
                    message = "network",
                    retryable = true,
                ),
            )

            val viewModel = SymptomIntakeViewModel(
                "subscription",
                repository,
            )

            viewModel.updateRawText("첫 번째 증상")
            viewModel.submit()
            advanceUntilIdle()

            viewModel.updateRawText("수정된 증상")
            viewModel.submit()
            advanceUntilIdle()

            assertEquals(2, repository.idempotencyKeys.size)
            assertTrue(
                repository.idempotencyKeys[0] !=
                    repository.idempotencyKeys[1],
            )
        }

    @Test
    fun stateConflict_keepsInputAndAppliesLatestStateSnapshot() = runTest(mainDispatcherRule.dispatcher) {
        val repository = RecordingInquiryRepository(
            createResult = ApiResult.Failure(
                code = "STATE-CONFLICT-01",
                message = "latest state",
                httpStatus = 409,
                conflict = StateConflictSnapshot(
                    currentStatus = "CONSULTATION_REQUIRED",
                    currentStateVersion = 4,
                    allowedActions = listOf("REQUEST_CONSULTATION".toCodeOnlyRuntimeAction()),
                ),
            )
        )
        val viewModel = SymptomIntakeViewModel("subscription", repository)
        viewModel.updateRawText("충돌 뒤에도 유지")
        viewModel.submit()
        advanceUntilIdle()

        val state = viewModel.state.value
        assertEquals("충돌 뒤에도 유지", state.rawText)
        assertEquals("CONSULTATION_REQUIRED", state.conflictStatus)
        assertEquals(4, state.conflictStateVersion)
        assertEquals(listOf("REQUEST_CONSULTATION"), state.conflictAllowedActions)
    }

    @Test
    fun unauthorizedFailure_keepsInputAndRequestsLogin() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = RecordingInquiryRepository(
                createResult = ApiResult.Failure(
                    code = "AUTH_REQUIRED",
                    message = "로그인이 만료되었습니다.",
                    httpStatus = 401,
                    retryable = false,
                ),
            )
            val viewModel = SymptomIntakeViewModel(
                "subscription",
                repository,
            )

            viewModel.updateRawText("로그인 만료 입력 유지")
            viewModel.submit()
            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals("로그인 만료 입력 유지", state.rawText)
            assertTrue(state.authExpired)
            assertFalse(state.retryable)
            assertFalse(state.isSubmitting)
            assertEquals(null, state.completed)
        }

    @Test
    fun clientFailures_keepInputWithoutRetry() =
        runTest(mainDispatcherRule.dispatcher) {
            val failures = listOf(
                Triple(400, "HTTP_400", "잘못된 요청"),
                Triple(403, "FORBIDDEN", "권한 부족"),
                Triple(404, "RESOURCE_NOT_FOUND", "정보 없음"),
            )

            failures.forEachIndexed { index, failure ->
                val repository = RecordingInquiryRepository(
                    createResult = ApiResult.Failure(
                        code = failure.second,
                        message = failure.third,
                        httpStatus = failure.first,
                        retryable = false,
                    ),
                )
                val viewModel = SymptomIntakeViewModel(
                    "subscription",
                    repository,
                )
                val input = "고객 오류 입력 $index"

                viewModel.updateRawText(input)
                viewModel.submit()
                advanceUntilIdle()

                val state = viewModel.state.value
                assertEquals(input, state.rawText)
                assertEquals(failure.third, state.globalError)
                assertFalse(state.retryable)
                assertFalse(state.authExpired)
                assertFalse(state.isSubmitting)
                assertEquals(null, state.completed)
            }
        }

    @Test
    fun serverAndTimeoutFailures_keepInputAndAllowRetry() =
        runTest(mainDispatcherRule.dispatcher) {
            val failures = listOf(
                503 to "AI-FAILED-01",
                504 to "AI-TIMEOUT-01",
            )

            failures.forEachIndexed { index, failure ->
                val repository = RecordingInquiryRepository(
                    createResult = ApiResult.Failure(
                        code = failure.second,
                        message = "일시적인 서버 오류",
                        httpStatus = failure.first,
                        retryable = true,
                    ),
                )
                val viewModel = SymptomIntakeViewModel(
                    "subscription",
                    repository,
                )
                val input = "서버 오류 입력 $index"

                viewModel.updateRawText(input)
                viewModel.submit()
                advanceUntilIdle()

                val state = viewModel.state.value
                assertEquals(input, state.rawText)
                assertTrue(state.retryable)
                assertFalse(state.authExpired)
                assertFalse(state.isSubmitting)
                assertEquals(null, state.completed)
            }
        }

    @Test
    fun authExpiration_canBeConsumedWithoutLosingDraft() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = RecordingInquiryRepository(
                createResult = ApiResult.Failure(
                    code = "AUTH_REQUIRED",
                    message = "로그인이 만료되었습니다.",
                    httpStatus = 401,
                    retryable = false,
                ),
            )

            val viewModel = SymptomIntakeViewModel(
                "subscription",
                repository,
            )

            viewModel.updateRawText("재로그인 후 복원할 입력")
            viewModel.submit()
            advanceUntilIdle()

            assertTrue(viewModel.state.value.authExpired)

            viewModel.consumeAuthExpiration()

            val state = viewModel.state.value
            assertFalse(state.authExpired)
            assertEquals(
                "재로그인 후 복원할 입력",
                state.rawText,
            )
            assertEquals(null, state.completed)
        }

    @Test
    fun success_preservesRuntimeIdentifiersVersionActionsAndCorrelationId() =
        runTest(mainDispatcherRule.dispatcher) {
            val action = AllowedAction(
                code = "CANCEL_INQUIRY",
                label = "문의 취소",
                operationId = "cancelInquiry",
                style = "DESTRUCTIVE",
                requiresConfirmation = true,
                confirmationMessage = "문의를 취소하시겠습니까?",
            )
            val repository = RecordingInquiryRepository(
                createResult = ApiResult.Success(
                    value = InquiryResponse(
                        inquiryId = "30000000-0000-4000-8000-000000000001",
                        inquiryCode = "INQ-001",
                        statusCode = "DRAFT",
                        stateVersion = 1,
                        idempotentReplay = false,
                        allowedActions = listOf(action),
                    ),
                    metadata = ResponseMetadata("correlation-1"),
                )
            )
            val viewModel = SymptomIntakeViewModel("subscription", repository)
            viewModel.updateRawText("출수량이 약합니다")
            viewModel.submit()
            advanceUntilIdle()

            val completed = viewModel.state.value.completed
            assertNotNull(completed)
            assertEquals("INQ-001", completed?.inquiryCode)
            assertEquals(1, completed?.stateVersion)
            assertEquals(listOf("CANCEL_INQUIRY"), completed?.allowedActionCodes)
            assertEquals("correlation-1", completed?.correlationId)
            assertTrue(repository.idempotencyKeys.single().isNotBlank())
        }

    private class RecordingInquiryRepository(
        var createResult: ApiResult<InquiryResponse>,
    ) : InquiryRepository {
        val idempotencyKeys = mutableListOf<String>()
        val requests = mutableListOf<CreateInquiryRequest>()

        override suspend fun create(
            request: CreateInquiryRequest,
            idempotencyKey: String,
        ): ApiResult<InquiryResponse> {
            requests += request
            idempotencyKeys += idempotencyKey
            return createResult
        }

        override suspend fun cancel(
            inquiryId: String,
            stateVersion: Int,
            reasonCode: String,
            reasonDetail: String?,
            idempotencyKey: String,
        ): ApiResult<CancelInquiryResponse> = error("unused")
    }
}
