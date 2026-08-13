package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryRequest
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerInquiryQuestionsDto
import com.skn29.watercare.core.model.CustomerInquirySnapshotDto
import com.skn29.watercare.core.model.DemoLoginRequest
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.LogoutResponse
import com.skn29.watercare.core.model.RefreshTokenRequest
import com.skn29.watercare.core.model.RequestConsultationResponseDto
import com.skn29.watercare.core.model.RequestConsultationResult
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.StateTransitionRequestDto
import com.skn29.watercare.core.model.SubmitFollowUpAnswersRequestDto
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResponseDto
import com.skn29.watercare.core.model.SubmitSymptomRequest
import com.skn29.watercare.core.model.SubmitSymptomResponse
import com.skn29.watercare.core.model.SubscriptionDetailDto
import com.skn29.watercare.core.model.SubscriptionListDataDto
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.network.WaterCareApi
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.ResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class RemoteCustomerInquiryRepositoryTest {
    @Test
    fun guidance_returnsPublishedBackendProjectionWithoutFakeFallback() = runBlocking {
        val api = RecordingWaterCareApi()
        val repository = RemoteCustomerInquiryRepository(api, Json { ignoreUnknownKeys = true })

        val result = repository.guidance(INQUIRY_ID)

        assertTrue(result is ApiResult.Success<*>)
        val guidance = (result as ApiResult.Success<GuidanceData>).value
        assertEquals(INQUIRY_ID, guidance.inquiryId)
        assertEquals("실제 AI 안내", guidance.usageGuidanceMessage)
        assertEquals(3, guidance.stateVersion)
        assertEquals(listOf(INQUIRY_ID), api.guidanceInquiryIds)
    }

    @Test
    fun consultationNetworkRetry_reusesKey_andSuccessUsesServerSnapshot() = runBlocking {
        val api = RecordingWaterCareApi(failFirstConsultation = true)
        var sequence = 0
        val repository = RemoteCustomerInquiryRepository(
            api = api,
            json = Json { ignoreUnknownKeys = true },
            consultationIdempotencyKeys = ConsultationRequestIdempotencyKeyStore {
                "consultation-key-${++sequence}"
            },
        )

        val first = repository.requestConsultation(INQUIRY_ID, 3)
        val retry = repository.requestConsultation(INQUIRY_ID, 3)
        val nextIntent = repository.requestConsultation(INQUIRY_ID, 3)

        assertTrue(first is ApiResult.Failure)
        assertTrue(retry is ApiResult.Success<*>)
        val success =
            (retry as ApiResult.Success<RequestConsultationResult>).value
        assertEquals("CONSULTATION_REQUIRED", success.statusCode)
        assertEquals(4, success.stateVersion)
        assertEquals(listOf(3, 3, 3), api.consultationStateVersions)
        assertEquals(api.consultationKeys[0], api.consultationKeys[1])
        assertNotEquals(api.consultationKeys[1], api.consultationKeys[2])
        assertTrue(nextIntent is ApiResult.Success<*>)
    }

    private class RecordingWaterCareApi(
        private val failFirstConsultation: Boolean = false,
    ) : WaterCareApi {
        val guidanceInquiryIds = mutableListOf<String>()
        val consultationKeys = mutableListOf<String>()
        val consultationStateVersions = mutableListOf<Int>()

        override suspend fun customerInquiryGuidance(
            inquiryId: String,
        ): Response<ApiEnvelope<GuidanceData>> {
            guidanceInquiryIds += inquiryId
            return Response.success(
                ApiEnvelope(
                    success = true,
                    data = GuidanceData(
                        inquiryId = inquiryId,
                        inquiryCode = "INQ-REMOTE-001",
                        statusCode = "AI_GUIDANCE",
                        stateVersion = 3,
                        symptomSummary = "출수량 감소",
                        riskLevel = "general",
                        usageGuidanceStatus = "NORMAL",
                        usageGuidanceMessage = "실제 AI 안내",
                        nextAction = "상담 요청",
                        requiresConsultation = false,
                        evidence = emptyList(),
                        allowedActions = listOf(
                            AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION)
                        ),
                    ),
                )
            )
        }

        override suspend fun requestConsultation(
            inquiryId: String,
            idempotencyKey: String,
            body: StateTransitionRequestDto,
        ): Response<ApiEnvelope<RequestConsultationResponseDto>> {
            consultationKeys += idempotencyKey
            consultationStateVersions += body.stateVersion
            if (failFirstConsultation && consultationKeys.size == 1) {
                throw java.io.IOException("test network failure")
            }
            return Response.success(
                ApiEnvelope(
                    success = true,
                    data = RequestConsultationResponseDto(
                        message = "상담 요청이 접수되었습니다.",
                        inquiryId = inquiryId,
                        status = "CONSULTATION_REQUIRED",
                        stateVersion = 4,
                        allowedActions = emptyList(),
                        idempotentReplay = consultationKeys.size > 2,
                    ),
                )
            )
        }

        override suspend fun health(): Response<ResponseBody> = unused()
        override suspend fun demoLogin(body: DemoLoginRequest): Response<ApiEnvelope<SessionResponse>> = unused()
        override suspend fun refresh(body: RefreshTokenRequest): Response<ApiEnvelope<SessionResponse>> = unused()
        override suspend fun logout(body: RefreshTokenRequest): Response<ApiEnvelope<LogoutResponse>> = unused()
        override suspend fun me(): Response<ApiEnvelope<UserData>> = unused()
        override suspend fun mySubscriptions(page: Int, size: Int): Response<ApiEnvelope<SubscriptionListDataDto>> = unused()
        override suspend fun mySubscription(subscriptionId: String): Response<ApiEnvelope<SubscriptionDetailDto>> = unused()
        override suspend fun createInquiry(idempotencyKey: String, body: CreateInquiryRequest): Response<ApiEnvelope<InquiryResponse>> = unused()
        override suspend fun submitSymptom(inquiryId: String, idempotencyKey: String, body: SubmitSymptomRequest): Response<ApiEnvelope<SubmitSymptomResponse>> = unused()
        override suspend fun cancelInquiry(inquiryId: String, idempotencyKey: String, body: CancelInquiryRequest): Response<ApiEnvelope<CancelInquiryResponse>> = unused()
        override suspend fun customerInquirySnapshot(inquiryId: String): Response<ApiEnvelope<CustomerInquirySnapshotDto>> = unused()
        override suspend fun customerInquiryQuestions(inquiryId: String): Response<ApiEnvelope<CustomerInquiryQuestionsDto>> = unused()
        override suspend fun submitFollowUpAnswers(inquiryId: String, idempotencyKey: String, body: SubmitFollowUpAnswersRequestDto): Response<ApiEnvelope<SubmitFollowUpAnswersResponseDto>> = unused()

        private fun <T> unused(): T = error("이 테스트에서는 사용하지 않습니다.")
    }

    companion object {
        private const val INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"
    }
}
