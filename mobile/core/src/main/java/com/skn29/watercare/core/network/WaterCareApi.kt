package com.skn29.watercare.core.network

import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.CarePrecheckSessionDto
import com.skn29.watercare.core.model.SaveCarePrecheckRequestDto
import com.skn29.watercare.core.model.StartCarePrecheckRequestDto
import com.skn29.watercare.core.model.SubmitCarePrecheckRequestDto
import com.skn29.watercare.core.model.CareHistoryCreateRequestDto
import com.skn29.watercare.core.model.CareHistoryItemDto
import com.skn29.watercare.core.model.CareHistoryListDataDto
import com.skn29.watercare.core.model.CareHistoryMutationResultDto
import com.skn29.watercare.core.model.CustomerActiveInquiryDataDto
import com.skn29.watercare.core.model.CancelInquiryRequest
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerInquiryQuestionsDto
import com.skn29.watercare.core.model.CustomerInquiryGuidanceDto
import com.skn29.watercare.core.model.CustomerInquiryConsultationResultDto
import com.skn29.watercare.core.model.CustomerInquirySnapshotDto
import com.skn29.watercare.core.model.DemoLoginRequest
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
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.LogoutResponse
import com.skn29.watercare.core.model.RefreshTokenRequest
import com.skn29.watercare.core.model.RequestConsultationRequestDto
import com.skn29.watercare.core.model.RequestConsultationResponseDto
import com.skn29.watercare.core.model.ReportUnresolvedRequestDto
import com.skn29.watercare.core.model.ResolutionFeedbackRequestDto
import com.skn29.watercare.core.model.ResolutionTransitionResponseDto
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
import retrofit2.http.PATCH
import retrofit2.http.Path
import retrofit2.http.Query

/** Only endpoints currently routed by backend/config/api_urls.py are declared here. */
interface WaterCareApi {
    @GET("health")
    suspend fun health(): Response<ResponseBody>

    @POST("api/v1/auth/demo-login")
    suspend fun demoLogin(@Body body: DemoLoginRequest): Response<ApiEnvelope<SessionResponse>>

    // -------------------------------------------------------
    // P1-A G2 CONFIRMED AUTH
    // Backend Runtime is implemented separately in G3.
    // -------------------------------------------------------

    @POST("api/v1/auth/contract-verification/challenges")
    suspend fun createContractVerificationChallenge(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: P1ChallengeRequest,
    ): Response<ApiEnvelope<P1ChallengeAccepted>>

    @POST("api/v1/auth/contract-verification/challenges/{challenge_id}/verify")
    suspend fun verifyContractVerificationChallenge(
        @Path("challenge_id") challengeId: String,
        @Body body: P1OtpVerificationRequest,
    ): Response<ApiEnvelope<P1ClaimTicket>>

    @POST("api/v1/auth/signup")
    suspend fun signupContractCustomer(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: P1SignupRequest,
    ): Response<ApiEnvelope<SessionResponse>>

    @POST("api/v1/auth/login")
    suspend fun loginWithPassword(
        @Body body: P1PasswordLoginRequest,
    ): Response<ApiEnvelope<SessionResponse>>

    @POST("api/v1/auth/account-recovery/username/challenges")
    suspend fun createUsernameRecoveryChallenge(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: P1ChallengeRequest,
    ): Response<ApiEnvelope<P1ChallengeAccepted>>

    @POST("api/v1/auth/account-recovery/username/challenges/{challenge_id}/verify")
    suspend fun verifyUsernameRecoveryChallenge(
        @Path("challenge_id") challengeId: String,
        @Body body: P1OtpVerificationRequest,
    ): Response<ApiEnvelope<P1UsernameRecoveryResult>>

    @POST("api/v1/auth/password-reset/challenges")
    suspend fun createPasswordResetChallenge(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: P1ChallengeRequest,
    ): Response<ApiEnvelope<P1ChallengeAccepted>>

    @POST("api/v1/auth/password-reset/challenges/{challenge_id}/verify")
    suspend fun verifyPasswordResetChallenge(
        @Path("challenge_id") challengeId: String,
        @Body body: P1OtpVerificationRequest,
    ): Response<ApiEnvelope<P1PasswordResetTicket>>

    @POST("api/v1/auth/password-reset/confirm")
    suspend fun confirmPasswordReset(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: P1PasswordResetConfirmRequest,
    ): Response<ApiEnvelope<P1PasswordResetResult>>

    @POST("api/v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshTokenRequest): Response<ApiEnvelope<SessionResponse>>

    @POST("api/v1/auth/logout")
    suspend fun logout(@Body body: RefreshTokenRequest): Response<ApiEnvelope<LogoutResponse>>

    @GET("api/v1/me")
    suspend fun me(): Response<ApiEnvelope<UserData>>

    @GET("api/v1/me/inquiries/active")
    suspend fun customerActiveInquiry(): Response<ApiEnvelope<CustomerActiveInquiryDataDto>>

    @GET("api/v1/me/subscriptions")
    suspend fun mySubscriptions(
        @Query("page") page: Int = 1,
        @Query("size") size: Int = 20,
    ): Response<ApiEnvelope<SubscriptionListDataDto>>

    @GET("api/v1/me/subscriptions/{subscriptionId}")
    suspend fun mySubscription(
        @Path("subscriptionId") subscriptionId: String,
    ): Response<ApiEnvelope<SubscriptionDetailDto>>

    @GET("api/v1/me/subscriptions/{subscriptionId}/care-records")
    suspend fun myCareRecords(
        @Path("subscriptionId") subscriptionId: String,
        @Query("page") page: Int = 1,
        @Query("size") size: Int = 20,
    ): Response<ApiEnvelope<CareHistoryListDataDto>>

    @GET("api/v1/me/subscriptions/{subscriptionId}/care-records/{careRecordId}")
    suspend fun myCareRecord(
        @Path("subscriptionId") subscriptionId: String,
        @Path("careRecordId") careRecordId: String,
    ): Response<ApiEnvelope<CareHistoryItemDto>>

    @POST("api/v1/me/subscriptions/{subscriptionId}/care-records")
    suspend fun createMyCareRecord(
        @Path("subscriptionId") subscriptionId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: CareHistoryCreateRequestDto,
    ): Response<ApiEnvelope<CareHistoryMutationResultDto>>

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

    @GET("api/v1/me/inquiries/{inquiryId}/guidance")
    suspend fun customerInquiryGuidance(
        @Path("inquiryId") inquiryId: String,
    ): Response<ApiEnvelope<CustomerInquiryGuidanceDto>>

    @GET("api/v1/me/inquiries/{inquiryId}/consultation-result")
    suspend fun customerInquiryConsultationResult(
        @Path("inquiryId") inquiryId: String,
    ): Response<ApiEnvelope<CustomerInquiryConsultationResultDto>>

    @POST("api/v1/inquiries/{inquiryId}/answers")
    suspend fun submitFollowUpAnswers(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: SubmitFollowUpAnswersRequestDto,
    ): Response<ApiEnvelope<SubmitFollowUpAnswersResponseDto>>
    // -------------------------------------------------------
    // T-021 CARE_PRECHECK
    // -------------------------------------------------------

    // ? ?? ?? ?? ??
    @POST("api/v1/me/questionnaire-sessions")
    suspend fun startCarePrecheck(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: StartCarePrecheckRequestDto,
    ): Response<ApiEnvelope<CarePrecheckSessionDto>>

    // ?? ?? ???
    //
    // ? ??? ?? ?? ?? ?
    // Backend? ??? ?? ??? ??? ? ?????.
    @GET("api/v1/me/questionnaire-sessions/{questionnaireSessionId}")
    suspend fun carePrecheckDetail(
        @Path("questionnaireSessionId")
        questionnaireSessionId: String,
    ): Response<ApiEnvelope<CarePrecheckSessionDto>>

    // ?? ? ?? ?? ??
    @PATCH("api/v1/me/questionnaire-sessions/{questionnaireSessionId}")
    suspend fun saveCarePrecheck(
        @Path("questionnaireSessionId")
        questionnaireSessionId: String,
        @Header("Idempotency-Key")
        idempotencyKey: String,
        @Body
        body: SaveCarePrecheckRequestDto,
    ): Response<ApiEnvelope<CarePrecheckSessionDto>>

    // ?? ??
    @POST(
        "api/v1/me/questionnaire-sessions/" +
            "{questionnaireSessionId}/submit"
    )
    suspend fun submitCarePrecheck(
        @Path("questionnaireSessionId")
        questionnaireSessionId: String,
        @Header("Idempotency-Key")
        idempotencyKey: String,
        @Body
        body: SubmitCarePrecheckRequestDto,
    ): Response<ApiEnvelope<CarePrecheckSessionDto>>

    @POST("api/v1/inquiries/{inquiryId}/request-consultation")
    suspend fun requestConsultation(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: RequestConsultationRequestDto,
    ): Response<ApiEnvelope<RequestConsultationResponseDto>>


    @POST("api/v1/inquiries/{inquiryId}/resolution-feedback")
    suspend fun submitResolutionFeedback(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: ResolutionFeedbackRequestDto,
    ): Response<ApiEnvelope<ResolutionTransitionResponseDto>>

    @POST("api/v1/inquiries/{inquiryId}/report-unresolved")
    suspend fun reportUnresolved(
        @Path("inquiryId") inquiryId: String,
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body body: ReportUnresolvedRequestDto,
    ): Response<ApiEnvelope<ResolutionTransitionResponseDto>>
}

interface RefreshApi {
    @POST("api/v1/auth/refresh")
    fun refreshSync(@Body body: RefreshTokenRequest): Call<ApiEnvelope<SessionResponse>>
}
