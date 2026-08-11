package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.SubmitSymptomResponse
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
