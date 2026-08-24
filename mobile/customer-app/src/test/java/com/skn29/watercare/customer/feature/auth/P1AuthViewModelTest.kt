package com.skn29.watercare.customer.feature.auth

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.P1ChallengeAccepted
import com.skn29.watercare.core.model.P1ChallengeRequest
import com.skn29.watercare.core.model.P1ClaimTicket
import com.skn29.watercare.core.model.P1OtpVerificationRequest
import com.skn29.watercare.core.model.P1PasswordLoginRequest
import com.skn29.watercare.core.model.P1PasswordResetConfirmRequest
import com.skn29.watercare.core.model.P1PasswordResetResult
import com.skn29.watercare.core.model.P1PasswordResetTicket
import com.skn29.watercare.core.model.P1SignupRequest
import com.skn29.watercare.core.model.P1UsernameRecoveryResult
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.P1AuthRepository
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
class P1AuthViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun productionLogin_trimsUsernameAndAuthenticatesCustomer() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository(
                loginResult = ApiResult.Success(customerSession())
            )
            val auth = FakeAuthRepository()

            val viewModel = AuthViewModel(
                authRepository = auth,
                backendStatusRepository = HealthyBackendStatusRepository,
                p1AuthRepository = p1,
            )
            advanceUntilIdle()

            viewModel.login(
                username = "  water.user  ",
                password = "Password1234",
            )
            advanceUntilIdle()

            assertEquals("water.user", p1.lastLoginRequest?.username)
            assertEquals("Password1234", p1.lastLoginRequest?.password)
            assertTrue(viewModel.state.value.authenticated)
            assertFalse(viewModel.state.value.offlinePreview)
        }

    @Test
    fun validation422_exposesFieldErrors() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository(
                loginResult = ApiResult.Failure(
                    code = "VALIDATION_ERROR",
                    message = "입력값을 확인해 주세요.",
                    httpStatus = 422,
                    fieldErrors = mapOf(
                        "username" to listOf("아이디 형식을 확인해 주세요."),
                        "password" to listOf("비밀번호를 확인해 주세요."),
                    ),
                )
            )

            val viewModel = AuthViewModel(
                authRepository = FakeAuthRepository(),
                backendStatusRepository = HealthyBackendStatusRepository,
                p1AuthRepository = p1,
            )
            advanceUntilIdle()

            viewModel.login("water.user", "Password1234")
            advanceUntilIdle()

            assertFalse(viewModel.state.value.authenticated)
            assertEquals(
                listOf("아이디 형식을 확인해 주세요."),
                viewModel.state.value.fieldErrors["username"],
            )
            assertEquals(
                listOf("비밀번호를 확인해 주세요."),
                viewModel.state.value.fieldErrors["password"],
            )
        }

    @Test
    fun rateLimit429_exposesRetryAfterSeconds() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository(
                loginResult = ApiResult.Failure(
                    code = "RATE_LIMITED",
                    message = "잠시 후 다시 시도해 주세요.",
                    httpStatus = 429,
                    retryable = true,
                    retryAfterSeconds = 60,
                )
            )

            val viewModel = AuthViewModel(
                authRepository = FakeAuthRepository(),
                backendStatusRepository = HealthyBackendStatusRepository,
                p1AuthRepository = p1,
            )
            advanceUntilIdle()

            viewModel.login("water.user", "Password1234")
            advanceUntilIdle()

            assertFalse(viewModel.state.value.authenticated)
            assertEquals(60, viewModel.state.value.retryAfterSeconds)
        }

    @Test
    fun passwordAndTokens_areNotExposedInAuthUiState() =
        runTest(mainDispatcherRule.dispatcher) {
            val password = "PASSWORD_SHOULD_NOT_APPEAR_1234"
            val accessToken = "ACCESS_TOKEN_SHOULD_NOT_APPEAR"
            val refreshToken = "REFRESH_TOKEN_SHOULD_NOT_APPEAR"

            val p1 = FakeP1AuthRepository(
                loginResult = ApiResult.Success(
                    customerSession(
                        accessToken = accessToken,
                        refreshToken = refreshToken,
                    )
                )
            )

            val viewModel = AuthViewModel(
                authRepository = FakeAuthRepository(),
                backendStatusRepository = HealthyBackendStatusRepository,
                p1AuthRepository = p1,
            )
            advanceUntilIdle()

            viewModel.login("water.user", password)
            advanceUntilIdle()

            val stateText = viewModel.state.value.toString()

            assertFalse(stateText.contains(password))
            assertFalse(stateText.contains(accessToken))
            assertFalse(stateText.contains(refreshToken))
        }

    @Test
    fun nonCustomerProductionLogin_isRejectedAndSessionIsCleared() =
        runTest(mainDispatcherRule.dispatcher) {
            val auth = FakeAuthRepository()
            val p1 = FakeP1AuthRepository(
                loginResult = ApiResult.Success(
                    customerSession(roleCode = "TECHNICIAN")
                )
            )

            val viewModel = AuthViewModel(
                authRepository = auth,
                backendStatusRepository = HealthyBackendStatusRepository,
                p1AuthRepository = p1,
            )
            advanceUntilIdle()

            viewModel.login("tech.user", "Password1234")
            advanceUntilIdle()

            assertFalse(viewModel.state.value.authenticated)
            assertEquals(1, auth.logoutCalls)
            assertEquals(
                "고객 계정으로 로그인해 주세요.",
                viewModel.state.value.error,
            )
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

    private class FakeAuthRepository : AuthRepository {
        var logoutCalls = 0

        override fun hasSession(): Boolean = false

        override suspend fun demoLogin(
            code: String,
        ): ApiResult<SessionResponse> =
            ApiResult.Failure(
                code = "UNUSED",
                message = "unused",
            )

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

    private class FakeP1AuthRepository(
        private val loginResult: ApiResult<SessionResponse>,
    ) : P1AuthRepository {

        var lastLoginRequest: P1PasswordLoginRequest? = null

        override suspend fun login(
            request: P1PasswordLoginRequest,
        ): ApiResult<SessionResponse> {
            lastLoginRequest = request
            return loginResult
        }

        override suspend fun createContractVerificationChallenge(
            request: P1ChallengeRequest,
            idempotencyKey: String,
        ): ApiResult<P1ChallengeAccepted> = unused()

        override suspend fun verifyContractVerificationChallenge(
            challengeId: String,
            request: P1OtpVerificationRequest,
        ): ApiResult<P1ClaimTicket> = unused()

        override suspend fun signup(
            request: P1SignupRequest,
            idempotencyKey: String,
        ): ApiResult<SessionResponse> = unused()

        override suspend fun createUsernameRecoveryChallenge(
            request: P1ChallengeRequest,
            idempotencyKey: String,
        ): ApiResult<P1ChallengeAccepted> = unused()

        override suspend fun verifyUsernameRecoveryChallenge(
            challengeId: String,
            request: P1OtpVerificationRequest,
        ): ApiResult<P1UsernameRecoveryResult> = unused()

        override suspend fun createPasswordResetChallenge(
            request: P1ChallengeRequest,
            idempotencyKey: String,
        ): ApiResult<P1ChallengeAccepted> = unused()

        override suspend fun verifyPasswordResetChallenge(
            challengeId: String,
            request: P1OtpVerificationRequest,
        ): ApiResult<P1PasswordResetTicket> = unused()

        override suspend fun confirmPasswordReset(
            request: P1PasswordResetConfirmRequest,
            idempotencyKey: String,
        ): ApiResult<P1PasswordResetResult> = unused()

        private fun <T> unused(): ApiResult<T> =
            ApiResult.Failure(
                code = "UNUSED",
                message = "unused",
            )
    }

    private object HealthyBackendStatusRepository : BackendStatusRepository {
        override suspend fun health(): ApiResult<Unit> =
            ApiResult.Success(Unit)
    }
}