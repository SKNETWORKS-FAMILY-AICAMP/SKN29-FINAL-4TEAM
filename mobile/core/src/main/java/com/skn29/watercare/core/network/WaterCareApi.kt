package com.skn29.watercare.core.network

import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.CancelInquiryRequest
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerInquiryQuestionsDto
import com.skn29.watercare.core.model.CustomerInquirySnapshotDto
import com.skn29.watercare.core.model.DemoLoginRequest
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.LogoutResponse
import com.skn29.watercare.core.model.RefreshTokenRequest
import com.skn29.watercare.core.model.RequestConsultationRequestDto
import com.skn29.watercare.core.model.RequestConsultationResponseDto
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.SubmitSymptomRequest
import com.skn29.watercare.core.model.SubmitFollowUpAnswersRequestDto
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResponseDto
import com.skn29.watercare.core.model.SubmitSymptomResponse
import com.skn29.watercare.core.model.SubscriptionDetailDto
import com.skn29.watercare.core.model.SubscriptionListDataDto
import com.skn29.watercare.core.model.UserData
import okhttp3.ResponseBody
import retrofit2.Call
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

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

    @GET("api/v1/me/subscriptions")
    suspend fun mySubscriptions(
        @Query("page") page: Int = 1,
        @Query("size") size: Int = 20,
    ): Response<ApiEnvelope<SubscriptionListDataDto>>

    @GET("api/v1/me/subscriptions/{subscriptionId}")
    suspend fun mySubscription(
        @Path("subscriptionId") subscriptionId: String,
    ): Response<ApiEnvelope<SubscriptionDetailDto>>

    @POST("api/v1/inquiries")
    suspend fun createInquiry(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: CreateInquiryRequest,
    ): Response<ApiEnvelope<InquiryResponse>>

    @POST("api/v1/inquiries/{inquiryId}/submit")
    suspend fun submitSymptom(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: SubmitSymptomRequest,
    ): Response<ApiEnvelope<SubmitSymptomResponse>>
    @POST("api/v1/inquiries/{inquiryId}/cancel")
    suspend fun cancelInquiry(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: CancelInquiryRequest,
    ): Response<ApiEnvelope<CancelInquiryResponse>>

    @GET("api/v1/me/inquiries/{inquiryId}")
    suspend fun customerInquirySnapshot(
        @Path("inquiryId") inquiryId: String,
    ): Response<ApiEnvelope<CustomerInquirySnapshotDto>>

    @GET("api/v1/me/inquiries/{inquiryId}/questions")
    suspend fun customerInquiryQuestions(
        @Path("inquiryId") inquiryId: String,
    ): Response<ApiEnvelope<CustomerInquiryQuestionsDto>>

    @POST("api/v1/inquiries/{inquiryId}/answers")
    suspend fun submitFollowUpAnswers(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: SubmitFollowUpAnswersRequestDto,
    ): Response<ApiEnvelope<SubmitFollowUpAnswersResponseDto>>
    @POST("api/v1/inquiries/{inquiryId}/request-consultation")
    suspend fun requestConsultation(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: RequestConsultationRequestDto,
    ): Response<ApiEnvelope<RequestConsultationResponseDto>>
}

interface RefreshApi {
    @POST("api/v1/auth/refresh")
    fun refreshSync(@Body body: RefreshTokenRequest): Call<ApiEnvelope<SessionResponse>>
}
