package com.skn29.watercare.core.repository

import com.skn29.watercare.core.auth.TokenStore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.AuthTokens
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
import com.skn29.watercare.core.network.WaterCareApi
import com.skn29.watercare.core.network.safeApiCall
import kotlinx.serialization.json.Json

interface P1AuthRepository {
    suspend fun createContractVerificationChallenge(
        request: P1ChallengeRequest,
        idempotencyKey: String,
    ): ApiResult<P1ChallengeAccepted>

    suspend fun verifyContractVerificationChallenge(
        challengeId: String,
        request: P1OtpVerificationRequest,
    ): ApiResult<P1ClaimTicket>

    suspend fun signup(
        request: P1SignupRequest,
        idempotencyKey: String,
    ): ApiResult<SessionResponse>

    suspend fun login(
        request: P1PasswordLoginRequest,
    ): ApiResult<SessionResponse>

    suspend fun createUsernameRecoveryChallenge(
        request: P1ChallengeRequest,
        idempotencyKey: String,
    ): ApiResult<P1ChallengeAccepted>

    suspend fun verifyUsernameRecoveryChallenge(
        challengeId: String,
        request: P1OtpVerificationRequest,
    ): ApiResult<P1UsernameRecoveryResult>

    suspend fun createPasswordResetChallenge(
        request: P1ChallengeRequest,
        idempotencyKey: String,
    ): ApiResult<P1ChallengeAccepted>

    suspend fun verifyPasswordResetChallenge(
        challengeId: String,
        request: P1OtpVerificationRequest,
    ): ApiResult<P1PasswordResetTicket>

    suspend fun confirmPasswordReset(
        request: P1PasswordResetConfirmRequest,
        idempotencyKey: String,
    ): ApiResult<P1PasswordResetResult>
}

class RemoteP1AuthRepository(
    private val api: WaterCareApi,
    private val tokenStore: TokenStore,
    private val json: Json,
) : P1AuthRepository {

    override suspend fun createContractVerificationChallenge(
        request: P1ChallengeRequest,
        idempotencyKey: String,
    ): ApiResult<P1ChallengeAccepted> =
        safeApiCall(json) {
            api.createContractVerificationChallenge(
                idempotencyKey = idempotencyKey,
                body = request,
            )
        }

    override suspend fun verifyContractVerificationChallenge(
        challengeId: String,
        request: P1OtpVerificationRequest,
    ): ApiResult<P1ClaimTicket> =
        safeApiCall(json) {
            api.verifyContractVerificationChallenge(
                challengeId = challengeId,
                body = request,
            )
        }

    override suspend fun signup(
        request: P1SignupRequest,
        idempotencyKey: String,
    ): ApiResult<SessionResponse> =
        saveSession(
            safeApiCall(json) {
                api.signupContractCustomer(
                    idempotencyKey = idempotencyKey,
                    body = request,
                )
            }
        )

    override suspend fun login(
        request: P1PasswordLoginRequest,
    ): ApiResult<SessionResponse> =
        saveSession(
            safeApiCall(json) {
                api.loginWithPassword(body = request)
            }
        )

    override suspend fun createUsernameRecoveryChallenge(
        request: P1ChallengeRequest,
        idempotencyKey: String,
    ): ApiResult<P1ChallengeAccepted> =
        safeApiCall(json) {
            api.createUsernameRecoveryChallenge(
                idempotencyKey = idempotencyKey,
                body = request,
            )
        }

    override suspend fun verifyUsernameRecoveryChallenge(
        challengeId: String,
        request: P1OtpVerificationRequest,
    ): ApiResult<P1UsernameRecoveryResult> =
        safeApiCall(json) {
            api.verifyUsernameRecoveryChallenge(
                challengeId = challengeId,
                body = request,
            )
        }

    override suspend fun createPasswordResetChallenge(
        request: P1ChallengeRequest,
        idempotencyKey: String,
    ): ApiResult<P1ChallengeAccepted> =
        safeApiCall(json) {
            api.createPasswordResetChallenge(
                idempotencyKey = idempotencyKey,
                body = request,
            )
        }

    override suspend fun verifyPasswordResetChallenge(
        challengeId: String,
        request: P1OtpVerificationRequest,
    ): ApiResult<P1PasswordResetTicket> =
        safeApiCall(json) {
            api.verifyPasswordResetChallenge(
                challengeId = challengeId,
                body = request,
            )
        }

    override suspend fun confirmPasswordReset(
        request: P1PasswordResetConfirmRequest,
        idempotencyKey: String,
    ): ApiResult<P1PasswordResetResult> =
        safeApiCall(json) {
            api.confirmPasswordReset(
                idempotencyKey = idempotencyKey,
                body = request,
            )
        }

    private suspend fun saveSession(
        result: ApiResult<SessionResponse>,
    ): ApiResult<SessionResponse> {
        if (result is ApiResult.Success) {
            tokenStore.save(
                AuthTokens(
                    accessToken = result.value.accessToken,
                    refreshToken = result.value.refreshToken,
                )
            )
        }
        return result
    }
}