package com.skn29.watercare.core.repository

import com.skn29.watercare.core.auth.TokenStore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.AuthTokens
import com.skn29.watercare.core.model.CancelInquiryRequest
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.DemoLoginRequest
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.RefreshTokenRequest
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.SubmitSymptomRequest
import com.skn29.watercare.core.model.SubmitSymptomResponse
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.network.WaterCareApi
import com.skn29.watercare.core.network.safeApiCall
import kotlinx.serialization.json.Json

interface AuthRepository {
    fun hasSession(): Boolean
    suspend fun demoLogin(code: String): ApiResult<SessionResponse>
    suspend fun logout(): ApiResult<Unit>
    suspend fun me(): ApiResult<UserData>
}

interface InquiryRepository {
    suspend fun create(
        request: CreateInquiryRequest,
        idempotencyKey: String,
    ): ApiResult<InquiryResponse>
    suspend fun submit(
        inquiryId: String,
        stateVersion: Int,
        idempotencyKey: String,
    ): ApiResult<SubmitSymptomResponse>

    suspend fun cancel(
        inquiryId: String,
        stateVersion: Int,
        reasonCode: String,
        reasonDetail: String?,
    ): ApiResult<CancelInquiryResponse>
}

class RemoteAuthRepository(
    private val api: WaterCareApi,
    private val tokenStore: TokenStore,
    private val json: Json,
) : AuthRepository {
    override fun hasSession(): Boolean = tokenStore.current() != null

    override suspend fun demoLogin(code: String): ApiResult<SessionResponse> =
        saveSession(safeApiCall(json) { api.demoLogin(DemoLoginRequest(code.trim())) })

    override suspend fun logout(): ApiResult<Unit> {
        val refresh = tokenStore.current()?.refreshToken
        if (refresh == null) {
            tokenStore.clear()
            return ApiResult.Success(Unit)
        }
        val result: ApiResult<com.skn29.watercare.core.model.LogoutResponse> =
            safeApiCall(json) { api.logout(RefreshTokenRequest(refresh)) }
        tokenStore.clear()
        return when (result) {
            is ApiResult.Success -> ApiResult.Success(Unit)
            is ApiResult.Failure -> result
        }
    }

    override suspend fun me(): ApiResult<UserData> = safeApiCall(json) { api.me() }

    private suspend fun saveSession(result: ApiResult<SessionResponse>): ApiResult<SessionResponse> {
        if (result is ApiResult.Success) {
            tokenStore.save(AuthTokens(result.value.accessToken, result.value.refreshToken))
        }
        return result
    }
}

class RemoteInquiryRepository(
    private val api: WaterCareApi,
    private val json: Json,
    private val cancelIdempotencyKeys: CancelIdempotencyKeyStore =
        CancelIdempotencyKeyStore(),
) : InquiryRepository {
    override suspend fun create(
        request: CreateInquiryRequest,
        idempotencyKey: String,
    ): ApiResult<InquiryResponse> =
        safeApiCall(json) { api.createInquiry(idempotencyKey, request) }

    override suspend fun submit(
        inquiryId: String,
        stateVersion: Int,
        idempotencyKey: String,
    ): ApiResult<SubmitSymptomResponse> =
        safeApiCall(json) {
            api.submitSymptom(
                inquiryId = inquiryId,
                idempotencyKey = idempotencyKey,
                body = SubmitSymptomRequest(stateVersion),
            )
        }
    override suspend fun cancel(
        inquiryId: String,
        stateVersion: Int,
        reasonCode: String,
        reasonDetail: String?,
    ): ApiResult<CancelInquiryResponse> {
        val operation = CancelOperationIdentity(
            inquiryId = inquiryId,
            stateVersion = stateVersion,
            reasonCode = reasonCode,
            reasonDetail = reasonDetail,
        )
        val idempotencyKey = cancelIdempotencyKeys.keyFor(operation)

        val result = safeApiCall(json) {
            api.cancelInquiry(
                inquiryId = inquiryId,
                idempotencyKey = idempotencyKey,
                body = CancelInquiryRequest(
                    stateVersion,
                    reasonCode,
                    reasonDetail,
                ),
            )
        }

        if (result is ApiResult.Success) {
            cancelIdempotencyKeys.complete(operation)
        }

        return result
    }
}
