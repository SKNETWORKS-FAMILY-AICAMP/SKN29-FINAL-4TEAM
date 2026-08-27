package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.CustomerInquiryConsultationResult
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.RequestConsultationResult
import com.skn29.watercare.core.model.ResolutionTransitionResponseDto
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.model.SymptomIntakeRequest
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.CustomerInquiryRepository
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
class ConsultationResultViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun completionPending_loadsConsultationResult_withoutGuidance() =
        runTest(mainDispatcherRule.dispatcher) {
            val care =
                RecordingCareRepository(
                    ApiResult.Success(guidanceData())
                )

            val remote =
                RecordingCustomerInquiryRepository(
                    snapshots = mutableListOf(
                        ApiResult.Success(
                            snapshot(
                                statusCode =
                                    "COMPLETION_PENDING",
                                stateVersion = 9,
                                allowedActions =
                                    resolutionActions(),
                            )
                        )
                    ),
                    consultationResultResponse =
                        ApiResult.Success(
                            consultationResult()
                        ),
                )

            val viewModel =
                GuidanceViewModel(
                    inquiryId = TEST_INQUIRY_ID,
                    scenario = MockScenario.NORMAL,
                    repository = care,
                    customerInquiryRepository =
                        remote,
                )

            advanceUntilIdle()

            assertTrue(
                viewModel.state.value is
                    GuidanceUiState
                        .ConsultationResult
            )
            assertEquals(0, care.guidanceCalls)
            assertEquals(1, remote.snapshotCalls)
            assertEquals(
                1,
                remote.consultationResultCalls,
            )

            val workflow =
                requireNotNull(
                    viewModel.workflowSnapshot.value
                )

            assertEquals(
                "COMPLETION_PENDING",
                workflow.statusCode,
            )
            assertEquals(9, workflow.stateVersion)
            assertEquals(
                2,
                workflow.allowedActions.size,
            )
        }

    @Test
    fun consultationResult409_doesNotFallbackToGuidance() =
        runTest(mainDispatcherRule.dispatcher) {
            val care =
                RecordingCareRepository(
                    ApiResult.Success(guidanceData())
                )

            val remote =
                RecordingCustomerInquiryRepository(
                    snapshots = mutableListOf(
                        ApiResult.Success(
                            snapshot(
                                statusCode =
                                    "COMPLETION_PENDING",
                                stateVersion = 9,
                                allowedActions =
                                    resolutionActions(),
                            )
                        )
                    ),
                    consultationResultResponse =
                        ApiResult.Failure(
                            code =
                                "CONSULTATION_RESULT_NOT_READY",
                            message =
                                "?? ?? ??? ?? ???? ?????.",
                            httpStatus = 409,
                            retryable = true,
                        ),
                )

            val viewModel =
                GuidanceViewModel(
                    inquiryId = TEST_INQUIRY_ID,
                    scenario = MockScenario.NORMAL,
                    repository = care,
                    customerInquiryRepository =
                        remote,
                )

            advanceUntilIdle()

            assertTrue(
                viewModel.state.value is
                    GuidanceUiState
                        .ConsultationResultNotReady
            )
            assertEquals(0, care.guidanceCalls)
            assertEquals(
                1,
                remote.consultationResultCalls,
            )
        }

    @Test
    fun consultationSuccess_replacesOldWorkflowActions() =
        runTest(mainDispatcherRule.dispatcher) {
            val requestAction =
                AllowedAction(
                    code =
                        InquiryActionLabels
                            .REQUEST_CONSULTATION
                )

            val care =
                RecordingCareRepository(
                    ApiResult.Success(guidanceData())
                )

            val remote =
                RecordingCustomerInquiryRepository(
                    snapshots = mutableListOf(
                        ApiResult.Success(
                            snapshot(
                                statusCode =
                                    "AI_GUIDANCE",
                                stateVersion = 3,
                                allowedActions =
                                    listOf(requestAction),
                            )
                        ),
                        ApiResult.Success(
                            snapshot(
                                statusCode =
                                    "AI_GUIDANCE",
                                stateVersion = 3,
                                allowedActions =
                                    listOf(requestAction),
                            )
                        ),
                        ApiResult.Success(
                            snapshot(
                                statusCode =
                                    "CONSULTATION_REQUIRED",
                                stateVersion = 4,
                                allowedActions =
                                    emptyList(),
                            )
                        ),
                    ),
                    requestConsultationResponse =
                        ApiResult.Success(
                            RequestConsultationResult(
                                message =
                                    "?? ??? ???????.",
                                inquiryId =
                                    TEST_INQUIRY_ID,
                                statusCode =
                                    "CONSULTATION_REQUIRED",
                                stateVersion = 4,
                                allowedActions =
                                    emptyList(),
                                idempotentReplay =
                                    false,
                            )
                        ),
                )

            val viewModel =
                GuidanceViewModel(
                    inquiryId = TEST_INQUIRY_ID,
                    scenario = MockScenario.NORMAL,
                    repository = care,
                    customerInquiryRepository =
                        remote,
                )

            advanceUntilIdle()

            viewModel.requestConsultation()
            advanceUntilIdle()

            assertTrue(
                viewModel.consultationState.value is
                    ConsultationRequestUiState.Success
            )

            val latest =
                requireNotNull(
                    viewModel.workflowSnapshot.value
                )

            assertEquals(
                "CONSULTATION_REQUIRED",
                latest.statusCode,
            )
            assertEquals(4, latest.stateVersion)
            assertTrue(
                latest.allowedActions.isEmpty()
            )
            assertEquals(
                1,
                remote.requestConsultationCalls,
            )
        }

    @Test
    fun resolution409_refreshesLatestSnapshot() =
        runTest(mainDispatcherRule.dispatcher) {
            val remote =
                RecordingCustomerInquiryRepository(
                    snapshots = mutableListOf(
                        ApiResult.Success(
                            snapshot(
                                statusCode =
                                    "COMPLETION_PENDING",
                                stateVersion = 9,
                                allowedActions =
                                    listOf(
                                        AllowedAction(
                                            code =
                                                InquiryActionLabels
                                                    .SUBMIT_RESOLUTION_FEEDBACK
                                        )
                                    ),
                            )
                        ),
                        ApiResult.Success(
                            snapshot(
                                statusCode =
                                    "RESOLVED",
                                stateVersion = 10,
                                allowedActions =
                                    emptyList(),
                            )
                        ),
                    ),
                    resolutionFeedbackResponse =
                        ApiResult.Failure(
                            code =
                                "STATE-CONFLICT-01",
                            message =
                                "?? ??? ???????.",
                            httpStatus = 409,
                            retryable = true,
                        ),
                )

            val viewModel =
                CustomerResolutionViewModel(
                    inquiryId = TEST_INQUIRY_ID,
                    repository = remote,
                )

            viewModel.markResolved()
            advanceUntilIdle()

            val state =
                viewModel.state.value as
                    CustomerResolutionUiState.Error

            assertTrue(
                state.message.contains(
                    "?? ??"
                )
            )

            val latest =
                requireNotNull(
                    viewModel.workflowSnapshot.value
                )

            assertEquals(
                "RESOLVED",
                latest.statusCode,
            )
            assertEquals(10, latest.stateVersion)
            assertTrue(
                latest.allowedActions.isEmpty()
            )
            assertEquals(2, remote.snapshotCalls)
        }

    @Test
    fun resolution422_hasDifferentValidationMessage() =
        runTest(mainDispatcherRule.dispatcher) {
            val remote =
                RecordingCustomerInquiryRepository(
                    snapshots = mutableListOf(
                        ApiResult.Success(
                            snapshot(
                                statusCode =
                                    "COMPLETION_PENDING",
                                stateVersion = 9,
                                allowedActions =
                                    listOf(
                                        AllowedAction(
                                            code =
                                                InquiryActionLabels
                                                    .CUSTOMER_REPORTED_UNRESOLVED
                                        )
                                    ),
                            )
                        )
                    ),
                    unresolvedResponse =
                        ApiResult.Failure(
                            code =
                                "VALIDATION_ERROR",
                            message =
                                "resolved ??? ?????.",
                            httpStatus = 422,
                            retryable = false,
                        ),
                )

            val viewModel =
                CustomerResolutionViewModel(
                    inquiryId = TEST_INQUIRY_ID,
                    repository = remote,
                )

            viewModel.reportUnresolved()
            advanceUntilIdle()

            val state =
                viewModel.state.value as
                    CustomerResolutionUiState.Error

            assertTrue(
                state.message.contains(
                    "????"
                )
            )
            assertFalse(state.retryable)
            assertEquals(1, remote.snapshotCalls)
        }

    private class RecordingCareRepository(
        private val guidanceResult:
            ApiResult<GuidanceData>,
    ) : CustomerCareRepository {
        var guidanceCalls = 0
            private set

        override suspend fun getGuidance(
            inquiryId: String,
            scenario: MockScenario,
        ): ApiResult<GuidanceData> {
            guidanceCalls += 1
            return guidanceResult
        }

        override suspend fun getHome():
            ApiResult<CustomerHomeData> =
            error("unused")

        override suspend fun submitIntake(
            request: SymptomIntakeRequest,
        ): ApiResult<IntakeSubmission> =
            error("unused")
    }

    private class RecordingCustomerInquiryRepository(
        private val snapshots:
            MutableList<
                ApiResult<CustomerInquirySnapshot>
            >,
        private val consultationResultResponse:
            ApiResult<CustomerInquiryConsultationResult> =
            ApiResult.Failure(
                code =
                    "CONSULTATION_RESULT_UNUSED",
                message = "unused",
            ),
        private val requestConsultationResponse:
            ApiResult<RequestConsultationResult> =
            ApiResult.Failure(
                code =
                    "REQUEST_CONSULTATION_UNUSED",
                message = "unused",
            ),
        private val resolutionFeedbackResponse:
            ApiResult<
                ResolutionTransitionResponseDto
            > =
            ApiResult.Failure(
                code =
                    "RESOLUTION_UNUSED",
                message = "unused",
            ),
        private val unresolvedResponse:
            ApiResult<
                ResolutionTransitionResponseDto
            > =
            ApiResult.Failure(
                code =
                    "UNRESOLVED_UNUSED",
                message = "unused",
            ),
    ) : CustomerInquiryRepository {
        var snapshotCalls = 0
            private set
        var consultationResultCalls = 0
            private set
        var requestConsultationCalls = 0
            private set

        override suspend fun snapshot(
            inquiryId: String,
        ): ApiResult<CustomerInquirySnapshot> {
            snapshotCalls += 1
            return snapshots.removeAt(0)
        }

        override suspend fun consultationResult(
            inquiryId: String,
        ): ApiResult<
            CustomerInquiryConsultationResult
        > {
            consultationResultCalls += 1
            return consultationResultResponse
        }

        override suspend fun questions(
            inquiryId: String,
        ): ApiResult<CustomerInquiryQuestions> =
            error("unused")

        override suspend fun submitAnswers(
            inquiryId: String,
            stateVersion: Int,
            answers: List<FollowUpAnswer>,
        ): ApiResult<
            SubmitFollowUpAnswersResult
        > =
            error("unused")

        override suspend fun requestConsultation(
            inquiryId: String,
            stateVersion: Int,
        ): ApiResult<RequestConsultationResult> {
            requestConsultationCalls += 1
            return requestConsultationResponse
        }

        override suspend fun submitResolutionFeedback(
            inquiryId: String,
            stateVersion: Int,
            comment: String?,
        ): ApiResult<
            ResolutionTransitionResponseDto
        > =
            resolutionFeedbackResponse

        override suspend fun reportUnresolved(
            inquiryId: String,
            stateVersion: Int,
            reasonCode: String?,
            comment: String?,
        ): ApiResult<
            ResolutionTransitionResponseDto
        > =
            unresolvedResponse
    }

    private companion object {
        const val TEST_INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"

        fun snapshot(
            statusCode: String,
            stateVersion: Int,
            allowedActions: List<AllowedAction>,
        ) =
            CustomerInquirySnapshot(
                inquiryId = TEST_INQUIRY_ID,
                statusCode = statusCode,
                stateVersion = stateVersion,
                subscriptionId =
                    "00000000-0000-4000-8000-000000000101",
                productModelCode =
                    "WPUJAC104DWH",
                allowedActions =
                    allowedActions,
                updatedAtRfc3339 =
                    "2026-08-27T13:30:00+09:00",
            )

        fun resolutionActions() =
            listOf(
                AllowedAction(
                    code =
                        InquiryActionLabels
                            .SUBMIT_RESOLUTION_FEEDBACK
                ),
                AllowedAction(
                    code =
                        InquiryActionLabels
                            .CUSTOMER_REPORTED_UNRESOLVED
                ),
            )

        fun consultationResult() =
            CustomerInquiryConsultationResult(
                inquiryId = TEST_INQUIRY_ID,
                statusCode =
                    "COMPLETION_PENDING",
                stateVersion = 9,
                resultCode =
                    "COMPLETED_NO_VISIT",
                resultDisplayLabel =
                    "?? ?? ??",
                customerGuidance =
                    "??? ?? ??? ? ???? ??? ???.",
                usageGuidanceStatus =
                    "NORMAL",
                usageGuidanceDisplayLabel =
                    "?? ?? ??",
                completedAt =
                    "2026-08-27T13:30:00+09:00",
                allowedActions =
                    resolutionActions(),
            )

        fun guidanceData() =
            GuidanceData(
                inquiryId = TEST_INQUIRY_ID,
                inquiryCode =
                    "INQ-GUIDANCE-TEST",
                statusCode =
                    "AI_GUIDANCE",
                stateVersion = 3,
                symptomSummary =
                    "??? ??",
                riskLevel = "general",
                usageGuidanceStatus =
                    "NORMAL",
                usageGuidanceMessage =
                    "??? ??",
                safeActions =
                    emptyList(),
                escalationConditions =
                    emptyList(),
                prohibitedActions =
                    emptyList(),
                nextAction =
                    "?? ??",
                requiresConsultation =
                    false,
                evidence =
                    emptyList(),
                allowedActions =
                    listOf(
                        AllowedAction(
                            code =
                                InquiryActionLabels
                                    .REQUEST_CONSULTATION
                        )
                    ),
            )
    }
}
