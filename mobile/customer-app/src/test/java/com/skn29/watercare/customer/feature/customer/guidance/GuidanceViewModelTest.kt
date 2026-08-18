package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.SubmitSymptomResponse
import com.skn29.watercare.core.model.SymptomIntakeRequest
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.repository.InquiryRepository
import com.skn29.watercare.customer.feature.customer.intake.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class GuidanceViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun noEvidenceScenario_becomesNoEvidenceState() =
        runTest(mainDispatcherRule.dispatcher) {
            val viewModel = GuidanceViewModel(
                inquiryId = "id",
                scenario = MockScenario.NO_EVIDENCE,
                repository = FakeCustomerCareRepository(),
            )
            advanceUntilIdle()
            assertTrue(
                viewModel.state.value is
                    GuidanceUiState.NoEvidence
            )
        }

    @Test
    fun guidanceNotReady409_offersExplicitReload_thenShowsGuidance() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = SequencedGuidanceRepository(
                mutableListOf(
                    ApiResult.Failure(
                        code = "AI_GUIDANCE_NOT_READY",
                        message = "AI 안내를 준비하고 있습니다.",
                        httpStatus = 409,
                        retryable = false,
                    ),
                    ApiResult.Success(remoteGuidance()),
                )
            )
            val viewModel = GuidanceViewModel(
                inquiryId = TEST_INQUIRY_ID,
                scenario = MockScenario.NORMAL,
                repository = repository,
            )
            advanceUntilIdle()

            val notReady = viewModel.state.value as GuidanceUiState.NotReady
            assertEquals("AI 안내를 준비하고 있습니다.", notReady.message)

            viewModel.load()
            advanceUntilIdle()

            val loaded = viewModel.state.value as GuidanceUiState.Content
            assertEquals("검증된 안전 안내", loaded.guidance.usageMessage)
            assertEquals(listOf("전원을 끄세요."), loaded.guidance.safeActions)
            assertEquals(
                InquiryActionLabels.REQUEST_CONSULTATION,
                loaded.guidance.allowedActions.single().code,
            )
            assertEquals(2, repository.calls)
        }

    @Test
    fun rapidDoubleConsultationRequest_callsWriteOnce() =
        runTest(mainDispatcherRule.dispatcher) {
            var snapshotCalls = 0
            var requestCalls = 0

            val snapshot =
                com.skn29.watercare.core.model.CustomerInquirySnapshot(
                    inquiryId = TEST_INQUIRY_ID,
                    statusCode = "AI_GUIDANCE",
                    stateVersion = 3,
                    subscriptionId =
                        "00000000-0000-4000-8000-000000000101",
                    productModelCode = "WPUJAC104DWH",
                    allowedActions = listOf(
                        AllowedAction(
                            code =
                                InquiryActionLabels
                                    .REQUEST_CONSULTATION,
                        )
                    ),
                    updatedAtRfc3339 =
                        "2026-08-17T16:00:00+09:00",
                )

            val remote =
                object :
                    com.skn29.watercare.core.repository.CustomerInquiryRepository {
                    override suspend fun snapshot(
                        inquiryId: String,
                    ): ApiResult<
                        com.skn29.watercare.core.model.CustomerInquirySnapshot
                    > {
                        snapshotCalls += 1
                        return ApiResult.Success(snapshot)
                    }

                    override suspend fun questions(
                        inquiryId: String,
                    ): ApiResult<
                        com.skn29.watercare.core.model.CustomerInquiryQuestions
                    > = error("unused")

                    override suspend fun submitAnswers(
                        inquiryId: String,
                        stateVersion: Int,
                        answers: List<
                            com.skn29.watercare.core.model.FollowUpAnswer
                        >,
                    ): ApiResult<
                        com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
                    > = error("unused")

                    override suspend fun requestConsultation(
                        inquiryId: String,
                        stateVersion: Int,
                    ): ApiResult<
                        com.skn29.watercare.core.model.RequestConsultationResult
                    > {
                        requestCalls += 1

                        return ApiResult.Failure(
                            code = "NETWORK_ERROR",
                            message = "network",
                            retryable = true,
                        )
                    }
                }

            val viewModel = GuidanceViewModel(
                inquiryId = TEST_INQUIRY_ID,
                scenario = MockScenario.NORMAL,
                repository = FakeCustomerCareRepository(),
                customerInquiryRepository = remote,
            )

            advanceUntilIdle()

            viewModel.requestConsultation()
            viewModel.requestConsultation()

            assertTrue(
                viewModel.consultationState.value is
                    ConsultationRequestUiState.Requesting
            )

            advanceUntilIdle()

            assertEquals(1, snapshotCalls)
            assertEquals(1, requestCalls)
        }

    @Test
    fun rapidDoubleCancel_callsRepositoryOnce() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository =
                RecordingInquiryRepository(
                    mutableListOf(
                        ApiResult.Success(
                            CancelInquiryResponse(
                                inquiryId = TEST_INQUIRY_ID,
                                state = "CANCELLED",
                                stateVersion = 3,
                                idempotentReplay = false,
                            )
                        )
                    )
                )

            val viewModel =
                newViewModel(inquiryRepository)

            viewModel.cancelInquiry(stateVersion = 2)
            viewModel.cancelInquiry(stateVersion = 2)

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
    fun cancelSuccess_usesBackendState() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository = RecordingInquiryRepository(
                mutableListOf(
                    ApiResult.Success(
                        CancelInquiryResponse(
                            inquiryId = TEST_INQUIRY_ID,
                            state = "CANCELLED",
                            stateVersion = 3,
                            idempotentReplay = false,
                        )
                    )
                )
            )
            val viewModel = newViewModel(inquiryRepository)

            viewModel.cancelInquiry(stateVersion = 2)
            advanceUntilIdle()

            val state =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Success
            assertEquals("CANCELLED", state.state)
            assertEquals(3, state.stateVersion)
            assertEquals(
                listOf(2),
                inquiryRepository.stateVersions,
            )
            assertEquals(
                listOf("CUSTOMER_REQUEST"),
                inquiryRepository.reasonCodes,
            )
        }

    @Test
    fun cancelConflict_withAllowedCancel_retriesLatestVersion() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository = RecordingInquiryRepository(
                mutableListOf(
                    ApiResult.Failure(
                        code = "STATE-CONFLICT-01",
                        message =
                            "다른 사용자가 문의 상태를 먼저 변경했습니다.",
                        httpStatus = 409,
                        conflict = StateConflictSnapshot(
                            currentStatus = "DRAFT",
                            currentStateVersion = 4,
                            allowedActions = listOf(
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
                            inquiryId = TEST_INQUIRY_ID,
                            state = "CANCELLED",
                            stateVersion = 5,
                            idempotentReplay = false,
                        )
                    ),
                )
            )
            val viewModel = newViewModel(inquiryRepository)

            viewModel.cancelInquiry(stateVersion = 2)
            advanceUntilIdle()

            val conflict =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Conflict
            assertTrue(conflict.canRetry)
            assertEquals(4, conflict.currentStateVersion)

            viewModel.retryCancelAfterConflict()
            advanceUntilIdle()

            assertTrue(
                viewModel.cancelState.value is
                    CancelInquiryUiState.Success
            )
            assertEquals(
                listOf(2, 4),
                inquiryRepository.stateVersions,
            )
        }

    @Test
    fun cancelledConflict_doesNotOfferRetry() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository = RecordingInquiryRepository(
                mutableListOf(
                    ApiResult.Failure(
                        code = "STATE-CONFLICT-01",
                        message = "이미 상태가 변경되었습니다.",
                        httpStatus = 409,
                        conflict = StateConflictSnapshot(
                            currentStatus = "CANCELLED",
                            currentStateVersion = 3,
                            allowedActions = emptyList(),
                        ),
                    )
                )
            )
            val viewModel = newViewModel(inquiryRepository)

            viewModel.cancelInquiry(stateVersion = 2)
            advanceUntilIdle()

            val conflict =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Conflict
            assertEquals("CANCELLED", conflict.currentStatus)
            assertEquals(false, conflict.canRetry)
        }

    @Test
    fun cancelNetworkFailure_isRetryableError() =
        runTest(mainDispatcherRule.dispatcher) {
            val inquiryRepository = RecordingInquiryRepository(
                mutableListOf(
                    ApiResult.Failure(
                        code = "NETWORK_ERROR",
                        message = "네트워크 오류",
                        retryable = true,
                    )
                )
            )
            val viewModel = newViewModel(inquiryRepository)

            viewModel.cancelInquiry(stateVersion = 2)
            advanceUntilIdle()

            val error =
                viewModel.cancelState.value as
                    CancelInquiryUiState.Error
            assertEquals("네트워크 오류", error.message)
            assertEquals(true, error.retryable)
        }

    private fun newViewModel(
        inquiryRepository: InquiryRepository,
    ) = GuidanceViewModel(
        inquiryId = TEST_INQUIRY_ID,
        scenario = MockScenario.NO_EVIDENCE,
        repository = FakeCustomerCareRepository(),
        inquiryRepository = inquiryRepository,
    )

    private fun remoteGuidance() = GuidanceData(
        inquiryId = TEST_INQUIRY_ID,
        inquiryCode = "INQ-GUIDANCE-301",
        statusCode = "AI_GUIDANCE",
        stateVersion = 3,
        symptomSummary = "누수 증상",
        riskLevel = "danger",
        usageGuidanceStatus = "TOTAL_STOP",
        usageGuidanceMessage = "검증된 안전 안내",
        safeActions = listOf("전원을 끄세요."),
        escalationConditions = listOf("누수가 계속되는 경우"),
        prohibitedActions = listOf("제품 분해"),
        nextAction = "상담 요청",
        requiresConsultation = true,
        evidence = emptyList(),
        allowedActions = listOf(
            AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION)
        ),
    )

    private class SequencedGuidanceRepository(
        private val results: MutableList<ApiResult<GuidanceData>>,
    ) : CustomerCareRepository {
        var calls: Int = 0
            private set

        override suspend fun getGuidance(
            inquiryId: String,
            scenario: MockScenario,
        ): ApiResult<GuidanceData> {
            calls += 1
            return results.removeAt(0)
        }

        override suspend fun getHome(): ApiResult<CustomerHomeData> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun submitIntake(
            request: SymptomIntakeRequest,
        ): ApiResult<IntakeSubmission> =
            error("이 테스트에서는 사용하지 않습니다.")
    }

    private class RecordingInquiryRepository(
        private val cancelResults:
            MutableList<ApiResult<CancelInquiryResponse>>,
    ) : InquiryRepository {
        val stateVersions = mutableListOf<Int>()
        val reasonCodes = mutableListOf<String>()

        override suspend fun create(
            request: CreateInquiryRequest,
            idempotencyKey: String,
        ): ApiResult<InquiryResponse> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun submit(
            inquiryId: String,
            stateVersion: Int,
            idempotencyKey: String,
        ): ApiResult<SubmitSymptomResponse> =
            error("이 테스트에서는 사용하지 않습니다.")

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
        private const val TEST_INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"
    }
}
