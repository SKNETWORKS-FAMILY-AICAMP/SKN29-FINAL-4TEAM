package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomIntakeRequest
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RemoteIntakeCustomerCareRepositoryTest {
    @Test
    fun retryWithSamePayload_reusesIdempotencyKey_andSuccessKeepsBackendState() = runBlocking {
        val inquiryRepository = RecordingInquiryRepository()
        val repository = RemoteIntakeCustomerCareRepository(
            inquiryRepository = inquiryRepository,
            fallbackRepository = EmptyFallbackRepository(),
        )
        val request = sampleRequest()

        val first = repository.submitIntake(request)
        val second = repository.submitIntake(request)
        val third = repository.submitIntake(request)

        assertTrue(first is ApiResult.Failure)
        assertTrue(second is ApiResult.Success<*>)
        assertTrue(third is ApiResult.Success<*>)

        assertEquals(inquiryRepository.keys[0], inquiryRepository.keys[1])
        assertNotEquals(inquiryRepository.keys[1], inquiryRepository.keys[2])

        val success = second as ApiResult.Success<IntakeSubmission>
        assertEquals("INQ-REMOTE-001", success.value.inquiryCode)
        assertEquals("QUESTIONNAIRE_IN_PROGRESS", success.value.statusCode)
        assertEquals(3, success.value.stateVersion)
        assertEquals("REQUEST_CONSULTATION", success.value.allowedActions.single().code)

        assertTrue(inquiryRepository.requests[0].rawText.contains("발생 조건:"))
        assertTrue(inquiryRepository.requests[0].rawText.contains("제품 표시 문구·오류 코드:"))
    }

    private fun sampleRequest() = SymptomIntakeRequest(
        subscriptionId = "00000000-0000-4000-8000-000000000101",
        symptomCodes = listOf("LOW_FLOW"),
        rawText = "출수량이 줄었습니다.",
        occurrenceCondition = "냉수 출수 시",
        displayText = "E01",
        entryMode = "ADHOC_INQUIRY",
        idempotencyKey = "legacy-ui-key",
    )

    private class RecordingInquiryRepository : InquiryRepository {
        val keys = mutableListOf<String>()
        val requests = mutableListOf<CreateInquiryRequest>()
        private var calls = 0

        override suspend fun create(
            request: CreateInquiryRequest,
            idempotencyKey: String,
        ): ApiResult<InquiryResponse> {
            keys += idempotencyKey
            requests += request
            calls += 1

            if (calls == 1) {
                return ApiResult.Failure(
                    code = "NETWORK_ERROR",
                    message = "재시도 가능한 테스트 오류",
                    retryable = true,
                )
            }

            return ApiResult.Success(
                InquiryResponse(
                    inquiryId = "00000000-0000-4000-8000-000000000301",
                    inquiryCode = "INQ-REMOTE-001",
                    statusCode = "QUESTIONNAIRE_IN_PROGRESS",
                    stateVersion = 3,
                    idempotentReplay = calls > 2,
                    allowedActions = listOf(
                        AllowedAction(
                            code = "REQUEST_CONSULTATION",
                            label = "상담 요청",
                            operationId = "request-consultation",
                            style = "PRIMARY",
                            requiresConfirmation = false,
                        )
                    ),
                )
            )
        }

        override suspend fun cancel(
            inquiryId: String,
            stateVersion: Int,
            reasonCode: String,
            reasonDetail: String?,
        ): ApiResult<CancelInquiryResponse> =
            error("이 테스트에서는 사용하지 않습니다.")
    }

    private class EmptyFallbackRepository : CustomerCareRepository {
        override suspend fun getHome(): ApiResult<CustomerHomeData> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun submitIntake(
            request: SymptomIntakeRequest,
        ): ApiResult<IntakeSubmission> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun getGuidance(
            inquiryId: String,
            scenario: MockScenario,
        ): ApiResult<GuidanceData> =
            error("이 테스트에서는 사용하지 않습니다.")
    }
}
