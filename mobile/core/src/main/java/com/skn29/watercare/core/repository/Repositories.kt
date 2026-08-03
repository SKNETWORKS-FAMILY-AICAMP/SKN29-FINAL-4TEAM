package com.skn29.watercare.core.repository

import com.skn29.watercare.core.auth.TokenStore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.AuthTokens
import com.skn29.watercare.core.model.DemoLoginRequest
import com.skn29.watercare.core.model.RefreshTokenRequest
import com.skn29.watercare.core.model.SessionResponse
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
            is ApiResult.Success -> ApiResult.Success(Unit, result.metadata)
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
