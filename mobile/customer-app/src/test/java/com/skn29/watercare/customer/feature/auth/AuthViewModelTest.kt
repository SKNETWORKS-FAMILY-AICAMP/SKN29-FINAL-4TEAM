package com.skn29.watercare.customer.feature.auth

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.P0_SYNTHETIC_CUSTOMER_LOGIN_CODE
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
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
class AuthViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun blankConfiguredCode_fallsBackToExistingDefault() =
        runTest(mainDispatcherRule.dispatcher) {
            val auth = FakeAuthRepository(customerSession())
            val viewModel = AuthViewModel(
                authRepository = auth,
                backendStatusRepository = HealthyBackendStatusRepository,
                demoCustomerCode = "   ",
            )
            advanceUntilIdle()

            viewModel.demoLogin()
            advanceUntilIdle()

            assertEquals(P0_SYNTHETIC_CUSTOMER_LOGIN_CODE, auth.lastDemoCode)
            assertTrue(viewModel.state.value.authenticated)
        }

    @Test
    fun configuredDemoCustomerCode_isUsedByCustomerLogin() =
        runTest(mainDispatcherRule.dispatcher) {
            val auth = FakeAuthRepository(customerSession())
            val viewModel = AuthViewModel(
                authRepository = auth,
                backendStatusRepository = HealthyBackendStatusRepository,
                demoCustomerCode = "DEMO-CUSTOMER-001",
            )
            advanceUntilIdle()

            viewModel.demoLogin()
            advanceUntilIdle()

            assertEquals("DEMO-CUSTOMER-001", auth.lastDemoCode)
            assertTrue(viewModel.state.value.authenticated)
        }

    @Test
    fun nonCustomerRole_isRejectedAndSessionIsCleared() =
        runTest(mainDispatcherRule.dispatcher) {
            val auth = FakeAuthRepository(customerSession(roleCode = "TECHNICIAN"))
            val viewModel = AuthViewModel(
                authRepository = auth,
                backendStatusRepository = HealthyBackendStatusRepository,
                demoCustomerCode = "DEMO-CUSTOMER-001",
            )
            advanceUntilIdle()

            viewModel.demoLogin()
            advanceUntilIdle()

            assertFalse(viewModel.state.value.authenticated)
            assertEquals(1, auth.logoutCalls)
            assertEquals("고객 계정으로 로그인해 주세요.", viewModel.state.value.error)
        }

    @Test
    fun sessionTokens_areNotExposedInAuthUiState() =
        runTest(mainDispatcherRule.dispatcher) {
            val accessToken = "TEST_ACCESS_TOKEN_SHOULD_NOT_APPEAR"
            val refreshToken = "TEST_REFRESH_TOKEN_SHOULD_NOT_APPEAR"
            val auth = FakeAuthRepository(
                customerSession(
                    accessToken = accessToken,
                    refreshToken = refreshToken,
                )
            )
            val viewModel = AuthViewModel(
                authRepository = auth,
                backendStatusRepository = HealthyBackendStatusRepository,
                demoCustomerCode = "DEMO-CUSTOMER-001",
            )
            advanceUntilIdle()

            viewModel.demoLogin()
            advanceUntilIdle()

            val stateText = viewModel.state.value.toString()
            assertFalse(stateText.contains(accessToken))
            assertFalse(stateText.contains(refreshToken))
        }

    private fun customerSession(
        roleCode: String = "CUSTOMER",
        accessToken: String = "test-access",
        refreshToken: String = "test-refresh",
    ) = SessionResponse(
        accessToken = accessToken,
        refreshToken = refreshToken,
        tokenType = "Bearer",
        accessExpiresIn = 900,
        refreshExpiresIn = 3600,
        user = UserData(
            id = "test-user",
            displayName = "테스트 사용자",
            roleCode = roleCode,
            isActive = true,
        ),
    )

    private class FakeAuthRepository(
        private val loginResult: SessionResponse,
    ) : AuthRepository {
        var lastDemoCode: String? = null
        var logoutCalls: Int = 0

        override fun hasSession(): Boolean = false

        override suspend fun demoLogin(code: String): ApiResult<SessionResponse> {
            lastDemoCode = code
            return ApiResult.Success(loginResult)
        }

        override suspend fun logout(): ApiResult<Unit> {
            logoutCalls += 1
            return ApiResult.Success(Unit)
        }

        override suspend fun me(): ApiResult<UserData> =
            ApiResult.Failure(
                code = "UNUSED",
                message = "unused",
            )
    }

    private object HealthyBackendStatusRepository : BackendStatusRepository {
        override suspend fun health(): ApiResult<Unit> = ApiResult.Success(Unit)
    }
}