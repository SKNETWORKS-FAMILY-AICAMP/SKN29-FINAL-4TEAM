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
class P1PasswordResetViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun startPasswordReset_trimsInputAndMovesToOtpStage() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startPasswordReset(
                customerNumber = "  CUSTOMER-001  ",
                contractNumber = "  CONTRACT-001  ",
            )
            advanceUntilIdle()

            assertEquals(
                "CUSTOMER-001",
                p1.lastResetChallengeRequest?.customerNumber,
            )
            assertEquals(
                "CONTRACT-001",
                p1.lastResetChallengeRequest?.contractNumber,
            )
            assertNotNull(p1.lastResetChallengeIdempotencyKey)

            assertEquals(
                PasswordResetStage.OTP_REQUIRED,
                viewModel.state.value.passwordResetStage,
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
    fun verifyPasswordResetOtp_keepsResetTicketOutOfUiState() =
        runTest(mainDispatcherRule.dispatcher) {
            val challengeId =
                "123e4567-e89b-12d3-a456-426614174000"
            val resetTicket =
                "reset-ticket-abcdefghijklmnopqrstuvwxyz-123456"

            val p1 = FakeP1AuthRepository(
                resetChallengeResult =
                    ApiResult.Success(
                        P1ChallengeAccepted(
                            challengeId = challengeId,
                            expiresIn = 300,
                            resendAfter = 60,
                            message = "인증번호를 전송했습니다.",
                        )
                    ),
                resetVerifyResult =
                    ApiResult.Success(
                        P1PasswordResetTicket(
                            resetTicket = resetTicket,
                            expiresIn = 300,
                        )
                    ),
            )

            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startPasswordReset(
                customerNumber = "CUSTOMER-001",
                contractNumber = "CONTRACT-001",
            )
            advanceUntilIdle()

            viewModel.verifyPasswordResetOtp("123456")
            advanceUntilIdle()

            assertEquals(
                challengeId,
                p1.lastVerifiedResetChallengeId,
            )
            assertEquals(
                "123456",
                p1.lastResetOtpRequest?.otpCode,
            )

            assertEquals(
                PasswordResetStage.PASSWORD_REQUIRED,
                viewModel.state.value.passwordResetStage,
            )
            assertEquals(
                300,
                viewModel.state.value
                    .passwordResetTicketExpiresInSeconds,
            )

            val stateText = viewModel.state.value.toString()

            assertFalse(stateText.contains(resetTicket))
            assertFalse(stateText.contains(challengeId))
            assertFalse(stateText.contains("123456"))
            assertFalse(stateText.contains("CUSTOMER-001"))
            assertFalse(stateText.contains("CONTRACT-001"))
        }

    @Test
    fun confirmPasswordReset_usesPrivateTicketAndMovesToResult() =
        runTest(mainDispatcherRule.dispatcher) {
            val resetTicket =
                "reset-ticket-abcdefghijklmnopqrstuvwxyz-123456"

            val p1 = FakeP1AuthRepository(
                resetVerifyResult =
                    ApiResult.Success(
                        P1PasswordResetTicket(
                            resetTicket = resetTicket,
                            expiresIn = 300,
                        )
                    ),
            )

            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startPasswordReset(
                customerNumber = "CUSTOMER-001",
                contractNumber = "CONTRACT-001",
            )
            advanceUntilIdle()

            viewModel.verifyPasswordResetOtp("123456")
            advanceUntilIdle()

            viewModel.confirmPasswordReset(
                newPassword = "waterbridge2026",
            )
            advanceUntilIdle()

            assertEquals(
                resetTicket,
                p1.lastConfirmRequest?.resetTicket,
            )
            assertEquals(
                "waterbridge2026",
                p1.lastConfirmRequest?.password,
            )
            assertNotNull(p1.lastConfirmIdempotencyKey)

            assertEquals(
                PasswordResetStage.RESULT,
                viewModel.state.value.passwordResetStage,
            )

            val stateText = viewModel.state.value.toString()

            assertFalse(stateText.contains(resetTicket))
            assertFalse(stateText.contains("waterbridge2026"))
        }

    @Test
    fun confirmPasswordReset_retryReusesSameIdempotencyKey() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository(
                confirmResults = mutableListOf(
                    ApiResult.Failure(
                        code = "TEMPORARY_ERROR",
                        message = "temporary failure",
                        retryable = true,
                    ),
                    ApiResult.Success(
                        P1PasswordResetResult(
                            passwordReset = true,
                            sessionsRevoked = true,
                        )
                    ),
                ),
            )

            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startPasswordReset(
                customerNumber = "CUSTOMER-001",
                contractNumber = "CONTRACT-001",
            )
            advanceUntilIdle()

            viewModel.verifyPasswordResetOtp("123456")
            advanceUntilIdle()

            viewModel.confirmPasswordReset(
                newPassword = "waterbridge2026",
            )
            advanceUntilIdle()

            assertEquals(1, p1.confirmIdempotencyKeys.size)

            viewModel.confirmPasswordReset(
                newPassword = "waterbridge2026",
            )
            advanceUntilIdle()

            assertEquals(2, p1.confirmIdempotencyKeys.size)
            assertEquals(
                p1.confirmIdempotencyKeys[0],
                p1.confirmIdempotencyKeys[1],
            )
            assertEquals(
                PasswordResetStage.RESULT,
                viewModel.state.value.passwordResetStage,
            )
        }

    @Test
    fun invalidPassword_isRejectedWithoutConfirmApiCall() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startPasswordReset(
                customerNumber = "CUSTOMER-001",
                contractNumber = "CONTRACT-001",
            )
            advanceUntilIdle()

            viewModel.verifyPasswordResetOtp("123456")
            advanceUntilIdle()

            viewModel.confirmPasswordReset(
                newPassword = "short123",
            )

            assertTrue(
                viewModel.state.value.fieldErrors["password"]
                    .isNullOrEmpty()
                    .not()
            )
            assertEquals(0, p1.confirmCalls)
        }

    @Test
    fun cancelPasswordReset_discardsTicketAndBlocksConfirm() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startPasswordReset(
                customerNumber = "CUSTOMER-001",
                contractNumber = "CONTRACT-001",
            )
            advanceUntilIdle()

            viewModel.verifyPasswordResetOtp("123456")
            advanceUntilIdle()

            viewModel.cancelPasswordReset()

            assertEquals(
                PasswordResetStage.IDLE,
                viewModel.state.value.passwordResetStage,
            )
            assertEquals(
                null,
                viewModel.state.value
                    .passwordResetTicketExpiresInSeconds,
            )

            viewModel.confirmPasswordReset(
                newPassword = "waterbridge2026",
            )

            assertEquals(0, p1.confirmCalls)
            assertTrue(
                viewModel.state.value.error
                    ?.contains("다시 진행") == true
            )
        }

    private fun newViewModel(
        p1: P1AuthRepository,
    ) = AuthViewModel(
        authRepository = FakeAuthRepository(),
        backendStatusRepository =
            HealthyBackendStatusRepository,
        p1AuthRepository = p1,
    )

    private class FakeP1AuthRepository(
        private val resetChallengeResult:
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
        private val resetVerifyResult:
            ApiResult<P1PasswordResetTicket> =
            ApiResult.Success(
                P1PasswordResetTicket(
                    resetTicket =
                        "reset-ticket-abcdefghijklmnopqrstuvwxyz-123456",
                    expiresIn = 300,
                )
            ),
        private val confirmResults:
            MutableList<ApiResult<P1PasswordResetResult>> =
            mutableListOf(
                ApiResult.Success(
                    P1PasswordResetResult(
                        passwordReset = true,
                        sessionsRevoked = true,
                    )
                )
            ),
    ) : P1AuthRepository {

        var lastResetChallengeRequest:
            P1ChallengeRequest? = null

        var lastResetChallengeIdempotencyKey:
            String? = null

        var lastVerifiedResetChallengeId:
            String? = null

        var lastResetOtpRequest:
            P1OtpVerificationRequest? = null

        var lastConfirmRequest:
            P1PasswordResetConfirmRequest? = null

        var lastConfirmIdempotencyKey:
            String? = null

        val confirmIdempotencyKeys =
            mutableListOf<String>()

        var confirmCalls = 0

        override suspend fun createPasswordResetChallenge(
            request: P1ChallengeRequest,
            idempotencyKey: String,
        ): ApiResult<P1ChallengeAccepted> {
            lastResetChallengeRequest = request
            lastResetChallengeIdempotencyKey =
                idempotencyKey
            return resetChallengeResult
        }

        override suspend fun verifyPasswordResetChallenge(
            challengeId: String,
            request: P1OtpVerificationRequest,
        ): ApiResult<P1PasswordResetTicket> {
            lastVerifiedResetChallengeId = challengeId
            lastResetOtpRequest = request
            return resetVerifyResult
        }

        override suspend fun confirmPasswordReset(
            request: P1PasswordResetConfirmRequest,
            idempotencyKey: String,
        ): ApiResult<P1PasswordResetResult> {
            confirmCalls += 1
            lastConfirmRequest = request
            lastConfirmIdempotencyKey = idempotencyKey
            confirmIdempotencyKeys += idempotencyKey

            return if (confirmResults.isNotEmpty()) {
                confirmResults.removeAt(0)
            } else {
                ApiResult.Failure(
                    code = "NO_RESULT",
                    message = "no result",
                )
            }
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

        override suspend fun createUsernameRecoveryChallenge(
            request: P1ChallengeRequest,
            idempotencyKey: String,
        ): ApiResult<P1ChallengeAccepted> = unused()

        override suspend fun verifyUsernameRecoveryChallenge(
            challengeId: String,
            request: P1OtpVerificationRequest,
        ): ApiResult<P1UsernameRecoveryResult> = unused()

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

        override suspend fun me(): ApiResult<UserData> =
            unused()

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