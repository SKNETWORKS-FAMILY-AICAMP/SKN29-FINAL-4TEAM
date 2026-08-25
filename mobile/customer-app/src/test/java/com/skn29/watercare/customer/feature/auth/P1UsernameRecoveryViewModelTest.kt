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
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class P1UsernameRecoveryViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun startUsernameRecovery_trimsInputAndMovesToOtpStage() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startUsernameRecovery(
                name = "  테스트 고객  ",
                email = "  TEST.USER@EXAMPLE.COM  ",
            )
            advanceUntilIdle()

            assertEquals(
                "테스트 고객",
                p1.lastRecoveryChallengeRequest?.name,
            )
            assertEquals(
                "test.user@example.com",
                p1.lastRecoveryChallengeRequest?.email,
            )
            assertEquals(
                null,
                p1.lastRecoveryChallengeRequest?.customerNumber,
            )
            assertEquals(
                null,
                p1.lastRecoveryChallengeRequest?.contractNumber,
            )
            assertNotNull(p1.lastRecoveryIdempotencyKey)

            assertEquals(
                UsernameRecoveryStage.OTP_REQUIRED,
                viewModel.state.value.usernameRecoveryStage,
            )
            assertEquals(
                300,
                viewModel.state.value.challengeExpiresInSeconds,
            )
            assertEquals(
                60,
                viewModel.state.value.resendAfterSeconds,
            )
        }

    @Test
    fun verifyUsernameRecoveryOtp_returnsMaskedUsernameWithoutSensitiveState() =
        runTest(mainDispatcherRule.dispatcher) {
            val challengeId =
                "123e4567-e89b-12d3-a456-426614174000"

            val p1 = FakeP1AuthRepository(
                recoveryChallengeResult =
                    ApiResult.Success(
                        P1ChallengeAccepted(
                            challengeId = challengeId,
                            expiresIn = 300,
                            resendAfter = 60,
                            message = "인증번호를 전송했습니다.",
                        )
                    ),
                recoveryVerifyResult =
                    ApiResult.Success(
                        P1UsernameRecoveryResult(
                            maskedUsername = "wa******er",
                        )
                    ),
            )

            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startUsernameRecovery(
                name = "테스트 고객",
                email = "test.user@example.com",
            )
            advanceUntilIdle()

            viewModel.verifyUsernameRecoveryOtp("123456")
            advanceUntilIdle()

            assertEquals(
                challengeId,
                p1.lastVerifiedRecoveryChallengeId,
            )
            assertEquals(
                "123456",
                p1.lastRecoveryOtpRequest?.otpCode,
            )

            assertEquals(
                UsernameRecoveryStage.RESULT,
                viewModel.state.value.usernameRecoveryStage,
            )
            assertEquals(
                "wa******er",
                viewModel.state.value.recoveredMaskedUsername,
            )

            val stateText = viewModel.state.value.toString()

            assertFalse(stateText.contains(challengeId))
            assertFalse(stateText.contains("123456"))
            assertFalse(stateText.contains("테스트 고객"))
            assertFalse(stateText.contains("test.user@example.com"))
        }

    @Test
    fun invalidOtp_isRejectedLocallyWithoutVerifyApiCall() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startUsernameRecovery(
                name = "테스트 고객",
                email = "test.user@example.com",
            )
            advanceUntilIdle()

            viewModel.verifyUsernameRecoveryOtp("12AB")

            assertTrue(
                viewModel.state.value.fieldErrors["otp_code"]
                    .isNullOrEmpty()
                    .not()
            )
            assertEquals(0, p1.recoveryVerifyCalls)
        }

    @Test
    fun rateLimit429_exposesRetryAfterSeconds() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository(
                recoveryChallengeResult =
                    ApiResult.Failure(
                        code = "TOO_MANY_REQUESTS",
                        message = "too many requests",
                        retryable = true,
                        retryAfterSeconds = 60,
                    )
            )

            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startUsernameRecovery(
                name = "테스트 고객",
                email = "test.user@example.com",
            )
            advanceUntilIdle()

            assertEquals(
                60,
                viewModel.state.value.retryAfterSeconds,
            )
            assertEquals(
                UsernameRecoveryStage.IDLE,
                viewModel.state.value.usernameRecoveryStage,
            )
        }

    @Test
    fun cancelUsernameRecovery_clearsFlowAndPreventsOtpVerification() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startUsernameRecovery(
                name = "테스트 고객",
                email = "test.user@example.com",
            )
            advanceUntilIdle()

            viewModel.cancelUsernameRecovery()

            assertEquals(
                UsernameRecoveryStage.IDLE,
                viewModel.state.value.usernameRecoveryStage,
            )
            assertEquals(
                null,
                viewModel.state.value.recoveredMaskedUsername,
            )

            viewModel.verifyUsernameRecoveryOtp("123456")

            assertEquals(0, p1.recoveryVerifyCalls)
            assertTrue(
                viewModel.state.value.error
                    ?.contains("다시 시작") == true
            )
        }


    @Test
    fun invalidUsernameRecoveryEmail_isRejectedBeforeApiCall() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startUsernameRecovery(
                name = "테스트 고객",
                email = "wrong-email",
            )

            advanceUntilIdle()

            assertEquals(
                listOf(
                    "올바른 이메일 주소를 입력해 주세요."
                ),
                viewModel.state.value
                    .fieldErrors["email"],
            )

            assertEquals(
                null,
                p1.lastRecoveryChallengeRequest,
            )

            assertEquals(
                UsernameRecoveryStage.IDLE,
                viewModel.state.value
                    .usernameRecoveryStage,
            )
        }

    private fun newViewModel(
        p1: P1AuthRepository,
    ) = AuthViewModel(
        authRepository = FakeAuthRepository(),
        backendStatusRepository = HealthyBackendStatusRepository,
        p1AuthRepository = p1,
    )

    private class FakeP1AuthRepository(
        private val recoveryChallengeResult:
            ApiResult<P1ChallengeAccepted> =
            ApiResult.Success(
                P1ChallengeAccepted(
                    challengeId =
                        "123e4567-e89b-12d3-a456-426614174000",
                    expiresIn = 300,
                    resendAfter = 60,
                    message = "인증번호를 전송했습니다.",
                )
            ),
        private val recoveryVerifyResult:
            ApiResult<P1UsernameRecoveryResult> =
            ApiResult.Success(
                P1UsernameRecoveryResult(
                    maskedUsername = "wa******er",
                )
            ),
    ) : P1AuthRepository {

        var lastRecoveryChallengeRequest:
            P1ChallengeRequest? = null

        var lastRecoveryIdempotencyKey:
            String? = null

        var lastVerifiedRecoveryChallengeId:
            String? = null

        var lastRecoveryOtpRequest:
            P1OtpVerificationRequest? = null

        var recoveryVerifyCalls = 0

        override suspend fun createUsernameRecoveryChallenge(
            request: P1ChallengeRequest,
            idempotencyKey: String,
        ): ApiResult<P1ChallengeAccepted> {
            lastRecoveryChallengeRequest = request
            lastRecoveryIdempotencyKey = idempotencyKey
            return recoveryChallengeResult
        }

        override suspend fun verifyUsernameRecoveryChallenge(
            challengeId: String,
            request: P1OtpVerificationRequest,
        ): ApiResult<P1UsernameRecoveryResult> {
            recoveryVerifyCalls += 1
            lastVerifiedRecoveryChallengeId = challengeId
            lastRecoveryOtpRequest = request
            return recoveryVerifyResult
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

        override suspend fun login(
            request: P1PasswordLoginRequest,
        ): ApiResult<SessionResponse> = unused()

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

    private class FakeAuthRepository : AuthRepository {
        override fun hasSession(): Boolean = false

        override suspend fun demoLogin(
            code: String,
        ): ApiResult<SessionResponse> = unused()

        override suspend fun logout(): ApiResult<Unit> =
            ApiResult.Success(Unit)

        override suspend fun me(): ApiResult<UserData> = unused()

        private fun <T> unused(): ApiResult<T> =
            ApiResult.Failure(
                code = "UNUSED",
                message = "unused",
            )
    }

    private object HealthyBackendStatusRepository :
        BackendStatusRepository {

        override suspend fun health(): ApiResult<Unit> =
            ApiResult.Success(Unit)
    }
}