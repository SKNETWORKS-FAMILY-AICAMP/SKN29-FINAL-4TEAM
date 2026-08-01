package com.skn29.watercare.customer.feature.customer.intake

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.repository.CustomerCareRepository
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SymptomIntakeViewModelTest {
    @get:Rule val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun failedSubmission_keepsInputAndAllowsRetry() = runTest(mainDispatcherRule.dispatcher) {
        val repository = object : CustomerCareRepository {
            override suspend fun getHome(): ApiResult<CustomerHomeData> = error("unused")
            override suspend fun submitIntake(request: com.skn29.watercare.core.model.SymptomIntakeRequest): ApiResult<IntakeSubmission> =
                ApiResult.Failure("NETWORK_ERROR", "network", retryable = true)
            override suspend fun getGuidance(inquiryId: String, scenario: MockScenario): ApiResult<GuidanceData> = error("unused")
        }
        val viewModel = SymptomIntakeViewModel("subscription", repository)
        viewModel.updateRawText("입력 유지 테스트")
        viewModel.submit()
        advanceUntilIdle()

        assertEquals("입력 유지 테스트", viewModel.state.value.rawText)
        assertFalse(viewModel.state.value.isSubmitting)
        assertNotNull(viewModel.state.value.globalError)
    }
    @Test
    fun stateConflict_keepsInputAndAppliesLatestStateSnapshot() = runTest(mainDispatcherRule.dispatcher) {
        val repository = object : CustomerCareRepository {
            override suspend fun getHome(): ApiResult<CustomerHomeData> = error("unused")
            override suspend fun submitIntake(request: com.skn29.watercare.core.model.SymptomIntakeRequest): ApiResult<IntakeSubmission> =
                ApiResult.Failure(
                    code = "STATE_CONFLICT",
                    message = "latest state",
                    httpStatus = 409,
                    conflict = StateConflictSnapshot(
                        currentStatus = "CONSULTATION_REQUIRED",
                        currentStateVersion = 4,
                        allowedActions = listOf("REQUEST_CONSULTATION"),
                    ),
                )
            override suspend fun getGuidance(inquiryId: String, scenario: MockScenario): ApiResult<GuidanceData> = error("unused")
        }
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

}
