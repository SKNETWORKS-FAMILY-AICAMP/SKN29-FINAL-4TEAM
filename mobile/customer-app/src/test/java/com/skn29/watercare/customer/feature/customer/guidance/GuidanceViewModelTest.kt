package com.skn29.watercare.customer.feature.customer.guidance

import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.customer.feature.customer.intake.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class GuidanceViewModelTest {
    @get:Rule val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun noEvidenceScenario_becomesNoEvidenceState() = runTest(mainDispatcherRule.dispatcher) {
        val viewModel = GuidanceViewModel("id", MockScenario.NO_EVIDENCE, FakeCustomerCareRepository())
        advanceUntilIdle()
        assertTrue(viewModel.state.value is GuidanceUiState.NoEvidence)
    }
}
