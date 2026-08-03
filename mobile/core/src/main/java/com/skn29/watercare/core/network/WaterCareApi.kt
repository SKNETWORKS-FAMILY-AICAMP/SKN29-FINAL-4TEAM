package com.skn29.watercare.core.network

import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.DemoLoginRequest
import com.skn29.watercare.core.model.LogoutResponse
import com.skn29.watercare.core.model.RefreshTokenRequest
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.UserData
import okhttp3.ResponseBody
import retrofit2.Call
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

/** Only endpoints currently routed by backend/config/api_urls.py are declared here. */
interface WaterCareApi {
    @GET("health")
    suspend fun health(): Response<ResponseBody>

    @POST("api/v1/auth/demo-login")
    suspend fun demoLogin(@Body body: DemoLoginRequest): Response<ApiEnvelope<SessionResponse>>

    @POST("api/v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshTokenRequest): Response<ApiEnvelope<SessionResponse>>

    @POST("api/v1/auth/logout")
    suspend fun logout(@Body body: RefreshTokenRequest): Response<ApiEnvelope<LogoutResponse>>

    @GET("api/v1/me")
    suspend fun me(): Response<ApiEnvelope<UserData>>

}

interface RefreshApi {
    @POST("api/v1/auth/refresh")
    fun refreshSync(@Body body: RefreshTokenRequest): Call<ApiEnvelope<SessionResponse>>
}
