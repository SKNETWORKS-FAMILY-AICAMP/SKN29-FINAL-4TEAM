package com.skn29.watercare.customer.feature.auth

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.P1ChallengeAccepted
import com.skn29.watercare.core.model.P1ChallengeRequest
import com.skn29.watercare.core.model.P1ClaimTicket
import com.skn29.watercare.core.model.P1ConsentCode
import com.skn29.watercare.core.model.P1ConsentRequest
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
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class P1SignupViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun contractVerification_movesToOtpStage() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()

            val viewModel = newViewModel(p1)
            advanceUntilIdle()

            viewModel.startSignupVerification(
                name = "  테스트 고객  ",
                email = "  TEST.USER@EXAMPLE.COM  ",
                username = "water.user",
                password = "Password1234",
            )
            advanceUntilIdle()

            assertEquals(
                "테스트 고객",
                p1.lastChallengeRequest?.name,
            )
            assertEquals(
                "test.user@example.com",
                p1.lastChallengeRequest?.email,
            )
            assertEquals(
                null,
                p1.lastChallengeRequest?.customerNumber,
            )
            assertEquals(
                null,
                p1.lastChallengeRequest?.contractNumber,
            )
            assertNotNull(p1.lastChallengeIdempotencyKey)

            assertEquals(
                SignupStage.OTP_REQUIRED,
                viewModel.state.value.signupStage,
            )
            assertEquals(300, viewModel.state.value.challengeExpiresInSeconds)
            assertEquals(60, viewModel.state.value.resendAfterSeconds)
        }

    @Test
    fun otpVerification_movesToAccountStageWithoutExposingSensitiveValues() =
        runTest(mainDispatcherRule.dispatcher) {
            val claimTicket = "CLAIM_TICKET_SHOULD_NOT_APPEAR_IN_UI_STATE_123456"
            val challengeId = "123e4567-e89b-12d3-a456-426614174000"

            val p1 = FakeP1AuthRepository(
                challengeResult = ApiResult.Success(
                    P1ChallengeAccepted(
                        challengeId = challengeId,
                        expiresIn = 300,
                        resendAfter = 60,
                        message = "인증번호를 전송했습니다.",
                    )
                ),
                verifyResult = ApiResult.Success(
                    P1ClaimTicket(
                        claimTicket = claimTicket,
                        expiresIn = 300,
                    )
                ),
            )

            val viewModel = newViewModel(p1)
            advanceUntilIdle()

            viewModel.startSignupVerification(
                name = "테스트 고객",
                email = "test.user@example.com",
                username = "water.user",
                password = "Password1234",
            )
            advanceUntilIdle()

            viewModel.verifySignupOtp("123456")
            advanceUntilIdle()

            assertEquals(challengeId, p1.lastVerifiedChallengeId)
            assertEquals("123456", p1.lastOtpRequest?.otpCode)

            assertEquals(
                SignupStage.ACCOUNT_REQUIRED,
                viewModel.state.value.signupStage,
            )

            val stateText = viewModel.state.value.toString()

            assertFalse(stateText.contains(challengeId))
            assertFalse(stateText.contains(claimTicket))
            assertFalse(stateText.contains("123456"))
            assertFalse(stateText.contains("테스트 고객"))
            assertFalse(stateText.contains("test.user@example.com"))
        }

    @Test
    fun completeSignup_returnsCustomerToLogin() =
        runTest(mainDispatcherRule.dispatcher) {
            val claimTicket = "CLAIM_TICKET_FOR_SIGNUP_12345678901234567890"
            val p1 = FakeP1AuthRepository(
                verifyResult = ApiResult.Success(
                    P1ClaimTicket(
                        claimTicket = claimTicket,
                        expiresIn = 300,
                    )
                ),
                signupResults = mutableListOf(
                    ApiResult.Success(customerSession())
                ),
            )

            val viewModel = newViewModel(p1)
            advanceUntilIdle()

            prepareVerifiedSignup(viewModel)

            val consents = requiredConsents()

            viewModel.completeSignup(
                username = "  water.user  ",
                password = "Password1234",
                consents = consents,
            )
            advanceUntilIdle()

            assertEquals(
                claimTicket,
                p1.lastSignupRequest?.claimTicket,
            )
            assertEquals(
                "테스트 고객",
                p1.lastSignupRequest?.name,
            )
            assertEquals(
                "test.user@example.com",
                p1.lastSignupRequest?.email,
            )
            assertEquals(
                "water.user",
                p1.lastSignupRequest?.username,
            )
            assertEquals("Password1234", p1.lastSignupRequest?.password)
            assertEquals(consents, p1.lastSignupRequest?.consents)
            assertNotNull(p1.lastSignupIdempotencyKey)

            assertFalse(
                viewModel.state.value.authenticated
            )
            assertFalse(
                viewModel.state.value.offlinePreview
            )
            assertEquals(
                "water.user",
                viewModel.state.value
                    .signupCompletedUsername,
            )

            viewModel.consumeSignupCompletion()

            assertEquals(
                null,
                viewModel.state.value
                    .signupCompletedUsername,
            )

            val stateText = viewModel.state.value.toString()
            assertFalse(stateText.contains(claimTicket))
            assertFalse(stateText.contains("Password1234"))
        }

    @Test
    fun signupRetry_reusesSameIdempotencyKey() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository(
                signupResults = mutableListOf(
                    ApiResult.Failure(
                        code = "NETWORK_ERROR",
                        message = "network",
                        retryable = true,
                    ),
                    ApiResult.Success(customerSession()),
                )
            )

            val viewModel = newViewModel(p1)
            advanceUntilIdle()

            prepareVerifiedSignup(viewModel)

            val consents = requiredConsents()

            viewModel.completeSignup(
                username = "water.user",
                password = "Password1234",
                consents = consents,
            )
            advanceUntilIdle()

            val firstKey = p1.signupIdempotencyKeys.single()

            viewModel.completeSignup(
                username = "water.user",
                password = "Password1234",
                consents = consents,
            )
            advanceUntilIdle()

            assertEquals(2, p1.signupIdempotencyKeys.size)
            assertEquals(firstKey, p1.signupIdempotencyKeys[1])
            assertFalse(
                viewModel.state.value.authenticated
            )
            assertEquals(
                "water.user",
                viewModel.state.value
                    .signupCompletedUsername,
            )
        }

    @Test
    fun completeSignup_rejectsInvalidPasswordAndMissingRequiredConsentsLocally() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)
            advanceUntilIdle()

            viewModel.completeSignup(
                username = "water.user",
                password = "short",
                consents = emptyList(),
            )

            assertTrue(
                viewModel.state.value.fieldErrors["password"]
                    .isNullOrEmpty()
                    .not()
            )
            assertTrue(
                viewModel.state.value.fieldErrors["terms"]
                    .isNullOrEmpty()
                    .not()
            )
            assertTrue(
                viewModel.state.value.fieldErrors["privacy"]
                    .isNullOrEmpty()
                    .not()
            )

            assertEquals(0, p1.signupCalls)
        }


    @Test
    fun invalidSignupEmail_isRejectedBeforeChallengeApiCall() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 = FakeP1AuthRepository()
            val viewModel = newViewModel(p1)

            advanceUntilIdle()

            viewModel.startSignupVerification(
                name = "테스트 고객",
                email = "invalid-email",
                username = "water.user",
                password = "Password1234",
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
                p1.lastChallengeRequest,
            )

            assertEquals(
                SignupStage.IDLE,
                viewModel.state.value.signupStage,
            )
        }

    @Test
    fun duplicateSignupEmail_fromBackend_isExposedAsEmailFieldError() =
        runTest(mainDispatcherRule.dispatcher) {
            val p1 =
                FakeP1AuthRepository(
                    challengeResult =
                        ApiResult.Failure(
                            code =
                                "EMAIL_ALREADY_EXISTS",
                            message =
                                "입력값을 확인해 주세요.",
                            httpStatus = 422,
                            fieldErrors =
                                mapOf(
                                    "email" to
                                        listOf(
                                            "이미 사용 중인 이메일입니다."
                                        )
                                ),
                        )
                )

            val viewModel =
                newViewModel(p1)

            advanceUntilIdle()

            viewModel.startSignupVerification(
                name = "테스트 고객",
                email =
                    "already.used@example.com",
                username = "water.user",
                password = "Password1234",
            )

            advanceUntilIdle()

            assertEquals(
                listOf(
                    "이미 사용 중인 이메일입니다."
                ),
                viewModel.state.value
                    .fieldErrors["email"],
            )

            assertEquals(
                SignupStage.IDLE,
                viewModel.state.value.signupStage,
            )

            assertEquals(
                "already.used@example.com",
                p1.lastChallengeRequest?.email,
            )
        }

    @Test
    fun resendSignupOtp_replacesOldChallengeAndVerifiesAgainstNewestOnly() =
        runTest(mainDispatcherRule.dispatcher) {
            val oldChallengeId =
                "123e4567-e89b-12d3-a456-426614174001"

            val newChallengeId =
                "123e4567-e89b-12d3-a456-426614174002"

            val p1 =
                FakeP1AuthRepository(
                    challengeResults =
                        mutableListOf(
                            ApiResult.Success(
                                P1ChallengeAccepted(
                                    challengeId =
                                        oldChallengeId,
                                    expiresIn = 300,
                                    resendAfter = 60,
                                    message =
                                        "인증번호를 전송했습니다.",
                                )
                            ),
                            ApiResult.Success(
                                P1ChallengeAccepted(
                                    challengeId =
                                        newChallengeId,
                                    expiresIn = 300,
                                    resendAfter = 60,
                                    message =
                                        "새 인증번호를 전송했습니다.",
                                )
                            ),
                        ),
                    verifyResults =
                        mutableListOf(
                            ApiResult.Failure(
                                code =
                                    "AUTH_VERIFICATION_FAILED",
                                message =
                                    "인증정보를 확인할 수 없습니다.",
                                httpStatus = 401,
                            ),
                            ApiResult.Success(
                                P1ClaimTicket(
                                    claimTicket =
                                        "ROTATED_CLAIM_TICKET_12345678901234567890",
                                    expiresIn = 300,
                                )
                            ),
                        ),
                )

            val viewModel =
                newViewModel(p1)

            advanceUntilIdle()

            viewModel.startSignupVerification(
                name = "테스트 고객",
                email =
                    "test.user@example.com",
                username = "water.user",
                password = "Password1234",
            )

            advanceUntilIdle()

            assertEquals(
                1,
                viewModel.state.value
                    .signupChallengeVersion,
            )

            viewModel.verifySignupOtp(
                "000000"
            )

            advanceUntilIdle()

            assertEquals(
                listOf(oldChallengeId),
                p1.verifiedChallengeIds,
            )

            val firstKey =
                p1.challengeIdempotencyKeys
                    .single()

            viewModel
                .resendSignupVerification()

            advanceUntilIdle()

            assertEquals(
                2,
                p1.challengeCalls,
            )

            assertEquals(
                2,
                viewModel.state.value
                    .signupChallengeVersion,
            )

            assertTrue(
                firstKey !=
                    p1.challengeIdempotencyKeys[1]
            )

            viewModel.verifySignupOtp(
                "222222"
            )

            advanceUntilIdle()

            assertEquals(
                listOf(
                    oldChallengeId,
                    newChallengeId,
                ),
                p1.verifiedChallengeIds,
            )

            assertEquals(
                newChallengeId,
                p1.lastVerifiedChallengeId,
            )

            assertEquals(
                SignupStage.ACCOUNT_REQUIRED,
                viewModel.state.value
                    .signupStage,
            )
        }

    @Test
    fun signupCredentialLengthLimits_rejectValuesOverTwentyLocally() =
        runTest(mainDispatcherRule.dispatcher) {
            val usernameRepository =
                FakeP1AuthRepository()

            val usernameViewModel =
                newViewModel(
                    usernameRepository
                )

            advanceUntilIdle()

            usernameViewModel
                .startSignupVerification(
                    name = "테스트 고객",
                    email =
                        "test.user@example.com",
                    username =
                        "a".repeat(21),
                    password =
                        "Password1234",
                )

            advanceUntilIdle()

            assertTrue(
                usernameViewModel.state.value
                    .fieldErrors["username"]
                    .isNullOrEmpty()
                    .not()
            )

            assertEquals(
                0,
                usernameRepository
                    .challengeCalls,
            )

            val passwordRepository =
                FakeP1AuthRepository()

            val passwordViewModel =
                newViewModel(
                    passwordRepository
                )

            advanceUntilIdle()

            passwordViewModel
                .startSignupVerification(
                    name = "테스트 고객",
                    email =
                        "test.user@example.com",
                    username =
                        "water.user",
                    password =
                        "a".repeat(20) + "1",
                )

            advanceUntilIdle()

            assertTrue(
                passwordViewModel.state.value
                    .fieldErrors["password"]
                    .isNullOrEmpty()
                    .not()
            )

            assertEquals(
                0,
                passwordRepository
                    .challengeCalls,
            )
        }

    private suspend fun TestScope.prepareVerifiedSignup(
        viewModel: AuthViewModel,
    ) {
        viewModel.startSignupVerification(
            name = "테스트 고객",
            email = "test.user@example.com",
            username = "water.user",
            password = "Password1234",
        )
        advanceUntilIdle()

        viewModel.verifySignupOtp("123456")
        advanceUntilIdle()
    }

    private fun requiredConsents() = listOf(
        P1ConsentRequest(
            code = P1ConsentCode.TERMS_OF_SERVICE,
            version = "TEST_VERSION",
            agreed = true,
        ),
        P1ConsentRequest(
            code = P1ConsentCode.PRIVACY_COLLECTION_USE,
            version = "TEST_VERSION",
            agreed = true,
        ),
    )

    private fun newViewModel(
        p1: P1AuthRepository,
    ) = AuthViewModel(
        authRepository = FakeAuthRepository(),
        backendStatusRepository = HealthyBackendStatusRepository,
        p1AuthRepository = p1,
    )

    private fun customerSession() = SessionResponse(
        accessToken = "test-access",
        refreshToken = "test-refresh",
        tokenType = "Bearer",
        accessExpiresIn = 900,
        refreshExpiresIn = 3600,
        user = UserData(
            id = "customer-user",
            displayName = "테스트 고객",
            roleCode = "CUSTOMER",
            isActive = true,
        ),
    )

    private class FakeP1AuthRepository(
        private val challengeResult: ApiResult<P1ChallengeAccepted> =
            ApiResult.Success(
                P1ChallengeAccepted(
                    challengeId = "123e4567-e89b-12d3-a456-426614174000",
                    expiresIn = 300,
                    resendAfter = 60,
                    message = "인증번호를 전송했습니다.",
                )
            ),
        private val verifyResult: ApiResult<P1ClaimTicket> =
            ApiResult.Success(
                P1ClaimTicket(
                    claimTicket = "DEFAULT_CLAIM_TICKET_12345678901234567890",
                    expiresIn = 300,
                )
            ),
        private val challengeResults:
            MutableList<ApiResult<P1ChallengeAccepted>>? =
                null,
        private val verifyResults:
            MutableList<ApiResult<P1ClaimTicket>>? =
                null,
        private val signupResults: MutableList<ApiResult<SessionResponse>> =
            mutableListOf(ApiResult.Success(defaultSession())),
    ) : P1AuthRepository {

        var lastChallengeRequest: P1ChallengeRequest? = null
        var lastChallengeIdempotencyKey: String? = null
        var lastVerifiedChallengeId: String? = null
        var lastOtpRequest: P1OtpVerificationRequest? = null
        var lastSignupRequest: P1SignupRequest? = null
        var lastSignupIdempotencyKey: String? = null

        val challengeIdempotencyKeys =
            mutableListOf<String>()

        val verifiedChallengeIds =
            mutableListOf<String>()

        var challengeCalls = 0
        var verifyCalls = 0

        val signupIdempotencyKeys =
            mutableListOf<String>()

        var signupCalls = 0

        override suspend fun createContractVerificationChallenge(
            request: P1ChallengeRequest,
            idempotencyKey: String,
        ): ApiResult<P1ChallengeAccepted> {
            challengeCalls += 1

            challengeIdempotencyKeys +=
                idempotencyKey

            lastChallengeRequest =
                request

            lastChallengeIdempotencyKey =
                idempotencyKey

            return if (
                challengeResults != null &&
                challengeResults.isNotEmpty()
            ) {
                challengeResults.removeAt(0)
            } else {
                challengeResult
            }
        }

        override suspend fun verifyContractVerificationChallenge(
            challengeId: String,
            request: P1OtpVerificationRequest,
        ): ApiResult<P1ClaimTicket> {
            verifyCalls += 1

            verifiedChallengeIds +=
                challengeId

            lastVerifiedChallengeId =
                challengeId

            lastOtpRequest = request

            return if (
                verifyResults != null &&
                verifyResults.isNotEmpty()
            ) {
                verifyResults.removeAt(0)
            } else {
                verifyResult
            }
        }

        override suspend fun signup(
            request: P1SignupRequest,
            idempotencyKey: String,
        ): ApiResult<SessionResponse> {
            signupCalls += 1
            lastSignupRequest = request
            lastSignupIdempotencyKey = idempotencyKey
            signupIdempotencyKeys += idempotencyKey

            return if (signupResults.isNotEmpty()) {
                signupResults.removeAt(0)
            } else {
                ApiResult.Failure(
                    code = "NO_TEST_RESULT",
                    message = "no test result",
                )
            }
        }

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

        companion object {
            private fun defaultSession() = SessionResponse(
                accessToken = "test-access",
                refreshToken = "test-refresh",
                tokenType = "Bearer",
                accessExpiresIn = 900,
                refreshExpiresIn = 3600,
                user = UserData(
                    id = "customer-user",
                    displayName = "테스트 고객",
                    roleCode = "CUSTOMER",
                    isActive = true,
                ),
            )
        }
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

    private object HealthyBackendStatusRepository : BackendStatusRepository {
        override suspend fun health(): ApiResult<Unit> =
            ApiResult.Success(Unit)
    }
}
