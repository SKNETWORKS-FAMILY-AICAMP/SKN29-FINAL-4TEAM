package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerInquiryQuestion
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.model.SubmitSymptomResponse
import com.skn29.watercare.core.repository.CustomerInquiryRepository
import com.skn29.watercare.core.repository.InquiryRepository
import com.skn29.watercare.customer.feature.customer.intake.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class FollowUpCancelViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun allowedQuestionnaire_cancelSuccess_usesCustomerRequestAndBlocksAnswerSubmit() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Success(
                            CancelInquiryResponse(
                                inquiryId = INQUIRY_ID,
                                state = "CANCELLED",
                                stateVersion = 3,
                                idempotentReplay = false,
                            )
                        )
                    )
                )

            val customerRepository =
                RecordingCustomerInquiryRepository(
                    snapshot = snapshot(
                        status = "QUESTIONNAIRE_IN_PROGRESS",
                        version = 2,
                        allowCancel = true,
                    ),
                )

            val viewModel =
                newViewModel(
                    customerRepository,
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(stateVersion = 2)
            advanceUntilIdle()

            val cancelled =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Success

            assertEquals("CANCELLED", cancelled.state)
            assertEquals(3, cancelled.stateVersion)
            assertEquals(listOf(2), inquiryRepository.stateVersions)
            assertEquals(
                listOf("CUSTOMER_REQUEST"),
                inquiryRepository.reasonCodes,
            )

            viewModel.submitAnswers()
            advanceUntilIdle()

            assertEquals(0, customerRepository.submitCalls)
        }

    @Test
    fun rapidDoubleCancel_callsRepositoryOnce() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Success(
                            CancelInquiryResponse(
                                inquiryId = INQUIRY_ID,
                                state = "CANCELLED",
                                stateVersion = 3,
                                idempotentReplay = false,
                            )
                        )
                    )
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = true,
                        ),
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(2)
            viewModel.cancelInquiry(2)

            assertTrue(
                viewModel.cancelState.value is
                    CancelInquiryUiState.Cancelling
            )

            advanceUntilIdle()

            assertEquals(
                listOf(2),
                inquiryRepository.stateVersions,
            )
        }

    @Test
    fun conflictWithCancelAction_retriesLatestStateVersion() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Failure(
                            code = "STATE-CONFLICT-01",
                            message = "문의 상태가 변경되었습니다.",
                            httpStatus = 409,
                            conflict =
                                StateConflictSnapshot(
                                    currentStatus =
                                        "QUESTIONNAIRE_IN_PROGRESS",
                                    currentStateVersion = 3,
                                    allowedActions =
                                        listOf(
                                            AllowedAction(
                                                code =
                                                    InquiryActionLabels
                                                        .CANCEL_INQUIRY
                                            )
                                        ),
                                ),
                        ),
                        ApiResult.Success(
                            CancelInquiryResponse(
                                inquiryId = INQUIRY_ID,
                                state = "CANCELLED",
                                stateVersion = 4,
                                idempotentReplay = false,
                            )
                        ),
                    )
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = true,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(2)
            advanceUntilIdle()

            val conflict =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Conflict

            assertTrue(conflict.canRetry)
            assertEquals(3, conflict.currentStateVersion)

            viewModel.retryCancelAfterConflict()
            advanceUntilIdle()

            assertTrue(
                viewModel.cancelState.value is
                    CancelInquiryUiState.Success
            )

            assertEquals(
                listOf(2, 3),
                inquiryRepository.stateVersions,
            )
        }

    @Test
    fun conflictWithoutCancelAction_doesNotRetry() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Failure(
                            code = "STATE-CONFLICT-01",
                            message = "문의 상태가 변경되었습니다.",
                            httpStatus = 409,
                            conflict =
                                StateConflictSnapshot(
                                    currentStatus = "CANCELLED",
                                    currentStateVersion = 3,
                                    allowedActions = emptyList(),
                                ),
                        )
                    )
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = true,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(2)
            advanceUntilIdle()

            val conflict =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Conflict

            assertFalse(conflict.canRetry)

            viewModel.retryCancelAfterConflict()
            advanceUntilIdle()

            assertEquals(
                listOf(2),
                inquiryRepository.stateVersions,
            )
        }

    @Test
    fun missingCancelAction_blocksCancelCall() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf()
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = false,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(2)
            advanceUntilIdle()

            assertTrue(
                viewModel.cancelState.value is
                    CancelInquiryUiState.Idle
            )

            assertTrue(
                inquiryRepository.stateVersions.isEmpty()
            )
        }

    @Test
    fun aiGuidance_blocksCancelEvenWhenActionIsInjected() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf()
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "AI_GUIDANCE",
                            version = 3,
                            allowCancel = true,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(3)
            advanceUntilIdle()

            assertTrue(
                viewModel.cancelState.value is
                    CancelInquiryUiState.Idle
            )

            assertTrue(
                inquiryRepository.stateVersions.isEmpty()
            )
        }

    @Test
    fun staleRequestedStateVersion_blocksCancelCall() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf()
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = true,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(1)
            advanceUntilIdle()

            assertTrue(
                inquiryRepository.stateVersions.isEmpty()
            )
        }

    @Test
    fun unauthorized401_setsAuthExpired() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Failure(
                            code = "UNAUTHORIZED",
                            message = "로그인이 만료되었습니다.",
                            httpStatus = 401,
                            retryable = false,
                        )
                    )
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = true,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(2)
            advanceUntilIdle()

            assertTrue(viewModel.authExpired.value)

            viewModel.consumeAuthExpired()

            assertFalse(viewModel.authExpired.value)
        }

    @Test
    fun notFound404_keepsNonRetryableErrorBoundary() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Failure(
                            code = "RESOURCE_NOT_FOUND",
                            message = "문의 정보를 찾을 수 없습니다.",
                            httpStatus = 404,
                            retryable = false,
                        )
                    )
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = true,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(2)
            advanceUntilIdle()

            val error =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Error

            assertFalse(error.retryable)
        }

    @Test
    fun networkFailure_keepsRetryableErrorBoundary() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Failure(
                            code = "NETWORK_ERROR",
                            message = "네트워크 오류",
                            retryable = true,
                        )
                    )
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = true,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(2)
            advanceUntilIdle()

            val error =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Error

            assertTrue(error.retryable)
        }

    @Test
    fun idempotentReplaySuccess_isSurfacedAsCancelled() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Success(
                            CancelInquiryResponse(
                                inquiryId = INQUIRY_ID,
                                state = "CANCELLED",
                                stateVersion = 3,
                                idempotentReplay = true,
                            )
                        )
                    )
                )

            val viewModel =
                newViewModel(
                    RecordingCustomerInquiryRepository(
                        snapshot = snapshot(
                            status = "QUESTIONNAIRE_IN_PROGRESS",
                            version = 2,
                            allowCancel = true,
                        )
                    ),
                    inquiryRepository,
                )

            advanceUntilIdle()

            viewModel.cancelInquiry(2)
            advanceUntilIdle()

            val success =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Success

            assertEquals("CANCELLED", success.state)
            assertTrue(success.idempotentReplay)
        }

    private fun newViewModel(
        customerRepository: CustomerInquiryRepository,
        inquiryRepository: InquiryRepository,
    ) =
        FollowUpQuestionsViewModel(
            inquiryId = INQUIRY_ID,
            repository = customerRepository,
            inquiryRepository = inquiryRepository,
        )

    private fun snapshot(
        status: String,
        version: Int,
        allowCancel: Boolean,
    ) =
        CustomerInquirySnapshot(
            inquiryId = INQUIRY_ID,
            statusCode = status,
            stateVersion = version,
            subscriptionId = SUBSCRIPTION_ID,
            productModelCode = "WPUJAC104DWH",
            allowedActions =
                if (allowCancel) {
                    listOf(
                        AllowedAction(
                            code =
                                InquiryActionLabels
                                    .CANCEL_INQUIRY,
                            label = "문의 취소",
                        )
                    )
                } else {
                    emptyList()
                },
            updatedAtRfc3339 =
                "2026-08-18T19:25:42+09:00",
        )

    private fun question() =
        CustomerInquiryQuestion(
            questionId = QUESTION_ID,
            questionType = "FREE_TEXT",
            prompt = "증상이 언제 시작됐나요?",
            required = true,
            options = emptyList(),
        )

    private class RecordingCustomerInquiryRepository(
        private val snapshot:
            CustomerInquirySnapshot,
    ) : CustomerInquiryRepository {
        var submitCalls = 0
            private set

        override suspend fun snapshot(
            inquiryId: String,
        ): ApiResult<CustomerInquirySnapshot> =
            ApiResult.Success(snapshot)

        override suspend fun questions(
            inquiryId: String,
        ): ApiResult<CustomerInquiryQuestions> =
            ApiResult.Success(
                CustomerInquiryQuestions(
                    inquiryId = INQUIRY_ID,
                    stateVersion =
                        snapshot.stateVersion,
                    questions = listOf(question()),
                )
            )

        override suspend fun submitAnswers(
            inquiryId: String,
            stateVersion: Int,
            answers: List<FollowUpAnswer>,
        ): ApiResult<SubmitFollowUpAnswersResult> {
            submitCalls += 1
            return error(
                "submitAnswers should not be called in cancel tests"
            )
        }

        private fun question() =
            CustomerInquiryQuestion(
                questionId = QUESTION_ID,
                questionType = "FREE_TEXT",
                prompt = "증상이 언제 시작됐나요?",
                required = true,
                options = emptyList(),
            )
    }

    private class RecordingInquiryRepository(
        private val cancelResults:
            MutableList<ApiResult<CancelInquiryResponse>>,
    ) : InquiryRepository {
        val stateVersions =
            mutableListOf<Int>()

        val reasonCodes =
            mutableListOf<String>()

        override suspend fun create(
            request: CreateInquiryRequest,
            idempotencyKey: String,
        ): ApiResult<InquiryResponse> =
            error("unused")

        override suspend fun submit(
            inquiryId: String,
            stateVersion: Int,
            idempotencyKey: String,
        ): ApiResult<SubmitSymptomResponse> =
            error("unused")

        override suspend fun cancel(
            inquiryId: String,
            stateVersion: Int,
            reasonCode: String,
            reasonDetail: String?,
        ): ApiResult<CancelInquiryResponse> {
            stateVersions += stateVersion
            reasonCodes += reasonCode
            return cancelResults.removeAt(0)
        }
    }

    companion object {
        private const val INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"

        private const val SUBSCRIPTION_ID =
            "00000000-0000-4000-8000-000000000101"

        private const val QUESTION_ID =
            "00000000-0000-4000-8000-000000000401"
    }
}
