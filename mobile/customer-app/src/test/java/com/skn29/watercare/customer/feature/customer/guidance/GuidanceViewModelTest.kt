package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.RequestConsultationResult
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.SubmitSymptomResponse
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.model.SymptomIntakeRequest
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.CustomerInquiryRepository
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
    fun guidanceNotReady_allowsExplicitReloadWithoutFakeFallback() =
        runTest(mainDispatcherRule.dispatcher) {
            val viewModel = GuidanceViewModel(
                inquiryId = TEST_INQUIRY_ID,
                scenario = MockScenario.BACKEND_PROCESSING,
                repository = NotReadyGuidanceRepository(),
            )
            advanceUntilIdle()

            val state = viewModel.state.value as GuidanceUiState.AiFailure
            assertEquals(true, state.retryable)
            assertEquals("AI_GUIDANCE", state.statusCode)
            assertEquals(3, state.stateVersion)
            assertEquals(
                InquiryActionLabels.REQUEST_CONSULTATION,
                state.allowedActions.single().normalizedCode,
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

    @Test
    fun consultationSuccess_usesServerWorkflowSnapshot() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = RecordingCustomerInquiryRepository(
                mutableListOf(
                    ApiResult.Success(
                        RequestConsultationResult(
                            message = "상담 요청이 접수되었습니다.",
                            inquiryId = TEST_INQUIRY_ID,
                            statusCode = "CONSULTATION_REQUIRED",
                            stateVersion = 4,
                            allowedActions = emptyList(),
                            idempotentReplay = false,
                        )
                    )
                )
            )
            val viewModel = newConsultationViewModel(repository)

            viewModel.requestConsultation(
                stateVersion = 3,
                allowedActions = listOf(
                    AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION)
                ),
            )
            advanceUntilIdle()

            val state = viewModel.consultationState.value as
                ConsultationRequestUiState.Success
            assertEquals("CONSULTATION_REQUIRED", state.statusCode)
            assertEquals(4, state.stateVersion)
            assertEquals(listOf(3), repository.stateVersions)
        }

    @Test
    fun consultationSuccess_blocksASecondRequestEvenIfServerActionRemains() =
        runTest(mainDispatcherRule.dispatcher) {
            val requestAction = AllowedAction(
                code = InquiryActionLabels.REQUEST_CONSULTATION
            )
            val repository = RecordingCustomerInquiryRepository(
                mutableListOf(
                    ApiResult.Success(
                        RequestConsultationResult(
                            message = "상담 요청이 접수되었습니다.",
                            inquiryId = TEST_INQUIRY_ID,
                            statusCode = "CONSULTATION_REQUIRED",
                            stateVersion = 4,
                            allowedActions = listOf(requestAction),
                            idempotentReplay = false,
                        )
                    )
                )
            )
            val viewModel = newConsultationViewModel(repository)

            viewModel.requestConsultation(3, listOf(requestAction))
            advanceUntilIdle()
            viewModel.requestConsultation(4, listOf(requestAction))
            advanceUntilIdle()

            assertTrue(
                viewModel.consultationState.value is
                    ConsultationRequestUiState.Success
            )
            assertEquals(listOf(3), repository.stateVersions)
        }

    @Test
    fun consultationSubmitting_blocksAnImmediateSecondRequest() =
        runTest(mainDispatcherRule.dispatcher) {
            val requestAction = AllowedAction(
                code = InquiryActionLabels.REQUEST_CONSULTATION
            )
            val repository = RecordingCustomerInquiryRepository(
                mutableListOf(
                    ApiResult.Success(
                        RequestConsultationResult(
                            message = "상담 요청이 접수되었습니다.",
                            inquiryId = TEST_INQUIRY_ID,
                            statusCode = "CONSULTATION_REQUIRED",
                            stateVersion = 4,
                            allowedActions = emptyList(),
                            idempotentReplay = false,
                        )
                    )
                )
            )
            val viewModel = newConsultationViewModel(repository)

            viewModel.requestConsultation(3, listOf(requestAction))
            viewModel.requestConsultation(3, listOf(requestAction))
            advanceUntilIdle()

            assertTrue(
                viewModel.consultationState.value is
                    ConsultationRequestUiState.Success
            )
            assertEquals(listOf(3), repository.stateVersions)
        }

    @Test
    fun consultationWithoutAllowedAction_neverCallsRemote() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = RecordingCustomerInquiryRepository(mutableListOf())
            val viewModel = newConsultationViewModel(repository)

            viewModel.requestConsultation(
                stateVersion = 3,
                allowedActions = emptyList(),
            )
            advanceUntilIdle()

            val state = viewModel.consultationState.value as
                ConsultationRequestUiState.Error
            assertEquals("ACTION_NOT_ALLOWED", state.code)
            assertTrue(repository.stateVersions.isEmpty())
        }

    @Test
    fun consultationConflict_explicitRetryUsesLatestServerVersion() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = RecordingCustomerInquiryRepository(
                mutableListOf(
                    ApiResult.Failure(
                        code = "STATE-CONFLICT-01",
                        message = "문의 상태가 변경되었습니다.",
                        httpStatus = 409,
                        conflict = StateConflictSnapshot(
                            currentStatus = "AI_GUIDANCE",
                            currentStateVersion = 4,
                            allowedActions = listOf(
                                AllowedAction(
                                    code = InquiryActionLabels.REQUEST_CONSULTATION
                                )
                            ),
                        ),
                    ),
                    ApiResult.Success(
                        RequestConsultationResult(
                            message = "상담 요청이 접수되었습니다.",
                            inquiryId = TEST_INQUIRY_ID,
                            statusCode = "CONSULTATION_REQUIRED",
                            stateVersion = 5,
                            allowedActions = emptyList(),
                            idempotentReplay = false,
                        )
                    ),
                )
            )
            val viewModel = newConsultationViewModel(repository)

            viewModel.requestConsultation(
                stateVersion = 3,
                allowedActions = listOf(
                    AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION)
                ),
            )
            advanceUntilIdle()
            val conflict = viewModel.consultationState.value as
                ConsultationRequestUiState.Conflict
            assertTrue(conflict.canRetry)

            viewModel.retryConsultationAfterConflict()
            advanceUntilIdle()

            assertTrue(
                viewModel.consultationState.value is
                    ConsultationRequestUiState.Success
            )
            assertEquals(listOf(3, 4), repository.stateVersions)
        }

    private fun newViewModel(
        inquiryRepository: InquiryRepository,
    ) = GuidanceViewModel(
        inquiryId = TEST_INQUIRY_ID,
        scenario = MockScenario.NO_EVIDENCE,
        repository = FakeCustomerCareRepository(),
        inquiryRepository = inquiryRepository,
    )

    private fun newConsultationViewModel(
        repository: CustomerInquiryRepository,
    ) = GuidanceViewModel(
        inquiryId = TEST_INQUIRY_ID,
        scenario = MockScenario.NO_EVIDENCE,
        repository = FakeCustomerCareRepository(),
        customerInquiryRepository = repository,
    )

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

    private class RecordingCustomerInquiryRepository(
        private val results: MutableList<ApiResult<RequestConsultationResult>>,
    ) : CustomerInquiryRepository {
        val stateVersions = mutableListOf<Int>()

        override suspend fun snapshot(
            inquiryId: String,
        ): ApiResult<CustomerInquirySnapshot> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun questions(
            inquiryId: String,
        ): ApiResult<CustomerInquiryQuestions> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun guidance(
            inquiryId: String,
        ): ApiResult<GuidanceData> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun submitAnswers(
            inquiryId: String,
            stateVersion: Int,
            answers: List<FollowUpAnswer>,
        ): ApiResult<SubmitFollowUpAnswersResult> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun requestConsultation(
            inquiryId: String,
            stateVersion: Int,
        ): ApiResult<RequestConsultationResult> {
            stateVersions += stateVersion
            return results.removeAt(0)
        }
    }

    private class NotReadyGuidanceRepository : CustomerCareRepository {
        override suspend fun getHome(): ApiResult<CustomerHomeData> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun submitIntake(
            request: SymptomIntakeRequest,
        ): ApiResult<IntakeSubmission> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun getGuidance(
            inquiryId: String,
            scenario: MockScenario,
        ): ApiResult<GuidanceData> = ApiResult.Failure(
            code = "AI_GUIDANCE_NOT_READY",
            message = "AI 안내가 아직 준비되지 않았습니다.",
            httpStatus = 409,
            retryable = false,
            conflict = StateConflictSnapshot(
                currentStatus = "AI_GUIDANCE",
                currentStateVersion = 3,
                allowedActions = listOf(
                    AllowedAction(
                        code = InquiryActionLabels.REQUEST_CONSULTATION
                    )
                ),
            ),
        )
    }

    companion object {
        private const val TEST_INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"
    }
}
