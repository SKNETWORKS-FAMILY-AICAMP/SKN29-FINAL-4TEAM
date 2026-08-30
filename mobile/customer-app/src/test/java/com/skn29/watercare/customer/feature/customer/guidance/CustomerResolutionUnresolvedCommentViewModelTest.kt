package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.ResolutionTransitionResponseDto
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.repository.CustomerInquiryRepository
import com.skn29.watercare.customer.feature.customer.intake.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CustomerResolutionUnresolvedCommentViewModelTest {
    @get:Rule
    val mainDispatcherRule =
        MainDispatcherRule()

    @Test
    fun unresolvedComment_isTrimmedAndForwarded() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val repository =
                RecordingRepository()

            val viewModel =
                CustomerResolutionViewModel(
                    inquiryId =
                        TEST_INQUIRY_ID,
                    repository =
                        repository,
                )

            viewModel.reportUnresolved(
                "  Water is still lukewarm.  "
            )

            advanceUntilIdle()

            assertEquals(
                1,
                repository.snapshotCalls,
            )

            assertEquals(
                1,
                repository.unresolvedCalls,
            )

            assertEquals(
                "STILL_UNRESOLVED",
                repository.lastReasonCode,
            )

            assertEquals(
                "Water is still lukewarm.",
                repository.lastComment,
            )
        }

    @Test
    fun unresolvedComment_isLimitedToOneThousandCharacters() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val repository =
                RecordingRepository()

            val viewModel =
                CustomerResolutionViewModel(
                    inquiryId =
                        TEST_INQUIRY_ID,
                    repository =
                        repository,
                )

            viewModel.reportUnresolved(
                "x".repeat(1200)
            )

            advanceUntilIdle()

            assertEquals(
                1000,
                repository
                    .lastComment
                    ?.length,
            )
        }

    @Test
    fun blankComment_isRejectedBeforeApiCall() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val repository =
                RecordingRepository()

            val viewModel =
                CustomerResolutionViewModel(
                    inquiryId =
                        TEST_INQUIRY_ID,
                    repository =
                        repository,
                )

            viewModel.reportUnresolved(
                "     "
            )

            advanceUntilIdle()

            assertEquals(
                0,
                repository.snapshotCalls,
            )

            assertEquals(
                0,
                repository.unresolvedCalls,
            )

            val state =
                viewModel.state.value as
                    CustomerResolutionUiState
                        .Error

            assertTrue(
                state.message.isNotBlank()
            )
        }

    private class RecordingRepository :
        CustomerInquiryRepository {
        var snapshotCalls = 0
            private set

        var unresolvedCalls = 0
            private set

        var lastReasonCode:
            String? = null
            private set

        var lastComment:
            String? = null
            private set

        override suspend fun snapshot(
            inquiryId: String,
        ): ApiResult<
            CustomerInquirySnapshot
        > {
            snapshotCalls += 1

            return ApiResult.Success(
                CustomerInquirySnapshot(
                    inquiryId =
                        TEST_INQUIRY_ID,
                    statusCode =
                        "COMPLETION_PENDING",
                    stateVersion = 9,
                    subscriptionId =
                        "00000000-0000-4000-8000-000000000101",
                    productModelCode =
                        "WPUJAC104DWH",
                    allowedActions =
                        listOf(
                            AllowedAction(
                                code =
                                    InquiryActionLabels
                                        .CUSTOMER_REPORTED_UNRESOLVED
                            )
                        ),
                    updatedAtRfc3339 =
                        "2026-08-28T17:00:00+09:00",
                )
            )
        }

        override suspend fun questions(
            inquiryId: String,
        ): ApiResult<
            CustomerInquiryQuestions
        > =
            error("unused")

        override suspend fun submitAnswers(
            inquiryId: String,
            stateVersion: Int,
            answers:
                List<FollowUpAnswer>,
        ): ApiResult<
            SubmitFollowUpAnswersResult
        > =
            error("unused")

        override suspend fun reportUnresolved(
            inquiryId: String,
            stateVersion: Int,
            reasonCode: String?,
            comment: String?,
        ): ApiResult<
            ResolutionTransitionResponseDto
        > {
            unresolvedCalls += 1

            lastReasonCode =
                reasonCode

            lastComment =
                comment

            return ApiResult.Failure(
                code =
                    "EXPECTED_TEST_FAILURE",
                message =
                    "expected",
                httpStatus = 422,
                retryable = false,
            )
        }
    }

    private companion object {
        const val TEST_INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"
    }
}
