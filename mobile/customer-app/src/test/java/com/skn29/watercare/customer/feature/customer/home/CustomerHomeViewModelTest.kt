package com.skn29.watercare.customer.feature.customer.home

import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.config.CustomerCareRuntimeConfig
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.customer.feature.customer.intake.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CustomerHomeViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun remoteMode_withoutDemoSubscriptionId_blocksIntake() =
        runTest(mainDispatcherRule.dispatcher) {
            val config = CustomerCareRuntimeConfig.from("REMOTE", "")
            val viewModel = createViewModel(config, offlinePreview = false)

            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals(CustomerCareMode.REMOTE, state.customerCareMode)
            assertFalse(state.intakeAvailable)
            assertTrue(state.intakeUnavailableReason.orEmpty().contains("DEMO_SUBSCRIPTION_ID"))
            assertTrue(state.dataSourceLabel.contains("UUID 미설정"))
        }

    @Test
    fun remoteMode_withDemoSubscriptionId_enablesIntake() =
        runTest(mainDispatcherRule.dispatcher) {
            val config = CustomerCareRuntimeConfig.from(
                "REMOTE",
                "11111111-2222-4333-8444-555555555555",
            )
            val viewModel = createViewModel(config, offlinePreview = false)

            advanceUntilIdle()

            val state = viewModel.state.value
            assertTrue(state.intakeAvailable)
            assertNull(state.intakeUnavailableReason)
            assertEquals(config.demoSubscriptionId, state.home?.subscriptionId)
            assertTrue(state.dataSourceLabel.contains("실제 API"))
        }

    @Test
    fun fakeMode_offlinePreview_keepsSyntheticIntakeAvailable() =
        runTest(mainDispatcherRule.dispatcher) {
            val config = CustomerCareRuntimeConfig.from("FAKE", "")
            val viewModel = createViewModel(config, offlinePreview = true)

            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals(CustomerCareMode.FAKE, state.customerCareMode)
            assertTrue(state.intakeAvailable)
            assertFalse(state.backendAvailable ?: true)
            assertTrue(state.dataSourceLabel.contains("Demo Mock"))
        }

    @Test
    fun remoteMode_offlinePreview_blocksAccidentalNetworkWrite() =
        runTest(mainDispatcherRule.dispatcher) {
            val config = CustomerCareRuntimeConfig.from(
                "REMOTE",
                "11111111-2222-4333-8444-555555555555",
            )
            val viewModel = createViewModel(config, offlinePreview = true)

            advanceUntilIdle()

            val state = viewModel.state.value
            assertFalse(state.intakeAvailable)
            assertTrue(state.intakeUnavailableReason.orEmpty().contains("FAKE"))
            assertTrue(state.dataSourceLabel.contains("문의 전송 차단"))
        }

    private fun createViewModel(
        config: CustomerCareRuntimeConfig,
        offlinePreview: Boolean,
    ) = CustomerHomeViewModel(
        authRepository = SuccessAuthRepository,
        careRepository = FakeCustomerCareRepository(config.fixtureSubscriptionId),
        backendStatusRepository = SuccessBackendStatusRepository,
        runtimeConfig = config,
        offlinePreview = offlinePreview,
    )

    private object SuccessBackendStatusRepository : BackendStatusRepository {
        override suspend fun health(): ApiResult<Unit> = ApiResult.Success(Unit)
    }

    private object SuccessAuthRepository : AuthRepository {
        override fun hasSession(): Boolean = true

        override suspend fun demoLogin(code: String): ApiResult<SessionResponse> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun logout(): ApiResult<Unit> = ApiResult.Success(Unit)

        override suspend fun me(): ApiResult<UserData> = ApiResult.Success(
            UserData(
                id = "user-id",
                displayName = "합성 고객",
                roleCode = "CUSTOMER",
                isActive = true,
            )
        )
    }
}
