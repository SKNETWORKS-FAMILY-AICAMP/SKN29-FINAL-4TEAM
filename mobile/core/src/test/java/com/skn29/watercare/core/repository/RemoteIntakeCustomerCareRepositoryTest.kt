package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.SubmitSymptomResponse
import com.skn29.watercare.core.model.SubscriptionDetailDto
import com.skn29.watercare.core.model.SubscriptionListDataDto
import com.skn29.watercare.core.model.SymptomIntakeRequest
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RemoteIntakeCustomerCareRepositoryTest {
    @Test
    fun createRetry_reusesCreateKey_thenSuccessfulFlowStartsNewOperation() = runBlocking {
        val inquiryRepository = RecordingInquiryRepository(failCreateCount = 1)
        val repository = RemoteIntakeCustomerCareRepository(
            inquiryRepository = inquiryRepository,
            subscriptionRepository = FailingSubscriptionRepository(),
        )
        val request = sampleRequest()

        val first = repository.submitIntake(request)
        val second = repository.submitIntake(request)
        val third = repository.submitIntake(request)

        assertTrue(first is ApiResult.Failure)
        assertTrue(second is ApiResult.Success<*>)
        assertTrue(third is ApiResult.Success<*>)

        assertEquals(inquiryRepository.createKeys[0], inquiryRepository.createKeys[1])
        assertNotEquals(inquiryRepository.createKeys[1], inquiryRepository.createKeys[2])
        assertNotEquals(inquiryRepository.submitKeys[0], inquiryRepository.submitKeys[1])

        val success = second as ApiResult.Success<IntakeSubmission>
        assertEquals("INQ-REMOTE-001", success.value.inquiryCode)
        assertEquals("QUESTIONNAIRE_IN_PROGRESS", success.value.statusCode)
        assertEquals(2, success.value.stateVersion)
        assertEquals("SUBMIT_ANSWERS", success.value.allowedActions.first().code)
        assertEquals(false, success.value.idempotentReplay)

        assertEquals("MOBILE", inquiryRepository.createRequests[0].channelCode)
        assertTrue(inquiryRepository.createRequests[0].rawText.contains("발생 조건:"))
        assertTrue(
            inquiryRepository.createRequests[0].rawText
                .contains("제품 표시 문구·오류 코드:")
        )
    }

    @Test
    fun submitRetry_doesNotCreateSecondInquiry_andReusesSubmitKey() = runBlocking {
        val inquiryRepository = RecordingInquiryRepository(failSubmitCount = 1)
        val repository = RemoteIntakeCustomerCareRepository(
            inquiryRepository = inquiryRepository,
            subscriptionRepository = FailingSubscriptionRepository(),
        )
        val request = sampleRequest()

        val first = repository.submitIntake(request)
        val second = repository.submitIntake(request)

        assertTrue(first is ApiResult.Failure)
        assertTrue(second is ApiResult.Success<*>)
        assertEquals(1, inquiryRepository.createCalls)
        assertEquals(2, inquiryRepository.submitCalls)
        assertEquals(inquiryRepository.submitKeys[0], inquiryRepository.submitKeys[1])
        assertEquals(listOf(1, 1), inquiryRepository.submittedStateVersions)
    }

    @Test
    fun staleConflict_retryUsesLatestVersionWithoutCreatingSecondInquiry() = runBlocking {
        val inquiryRepository = RecordingInquiryRepository(staleConflictCount = 1)
        val repository = RemoteIntakeCustomerCareRepository(
            inquiryRepository = inquiryRepository,
            subscriptionRepository = FailingSubscriptionRepository(),
        )
        val request = sampleRequest()

        val first = repository.submitIntake(request)
        val second = repository.submitIntake(request)

        assertTrue(first is ApiResult.Failure)
        assertTrue(second is ApiResult.Success<*>)
        assertEquals(1, inquiryRepository.createCalls)
        assertEquals(2, inquiryRepository.submitCalls)
        assertEquals(listOf(1, 2), inquiryRepository.submittedStateVersions)
        assertEquals(inquiryRepository.submitKeys[0], inquiryRepository.submitKeys[1])
    }

    @Test
    fun guidanceWithoutBackendRoute_failsClosed() = runBlocking {
        val repository = RemoteIntakeCustomerCareRepository(
            inquiryRepository = RecordingInquiryRepository(),
            subscriptionRepository = FailingSubscriptionRepository(),
        )

        val result = repository.getGuidance(
            inquiryId = "00000000-0000-4000-8000-000000000301",
            scenario = MockScenario.NORMAL,
        )

        assertTrue(result is ApiResult.Failure)
        val failure = result as ApiResult.Failure
        assertEquals("GUIDANCE_ROUTE_UNAVAILABLE", failure.code)
        assertEquals(false, failure.retryable)
    }

    @Test
    fun remoteHome_subscriptionFailureIsReturned_withoutFixtureFallback() = runBlocking {
        val repository = RemoteIntakeCustomerCareRepository(
            inquiryRepository = RecordingInquiryRepository(),
            subscriptionRepository = FailingSubscriptionRepository(),
        )

        val result = repository.getHome()

        assertTrue(result is ApiResult.Failure)
        val failure = result as ApiResult.Failure
        assertEquals("SUBSCRIPTION_REMOTE_FAILURE", failure.code)
        assertEquals(true, failure.retryable)
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

    private class RecordingInquiryRepository(
        private val failCreateCount: Int = 0,
        private val failSubmitCount: Int = 0,
        private val staleConflictCount: Int = 0,
    ) : InquiryRepository {
        val createKeys = mutableListOf<String>()
        val submitKeys = mutableListOf<String>()
        val createRequests = mutableListOf<CreateInquiryRequest>()
        val submittedStateVersions = mutableListOf<Int>()
        var createCalls = 0
            private set
        var submitCalls = 0
            private set

        override suspend fun create(
            request: CreateInquiryRequest,
            idempotencyKey: String,
        ): ApiResult<InquiryResponse> {
            createCalls += 1
            createKeys += idempotencyKey
            createRequests += request

            if (createCalls <= failCreateCount) {
                return ApiResult.Failure(
                    code = "NETWORK_ERROR",
                    message = "문의 생성 재시도 테스트 오류",
                    retryable = true,
                )
            }

            return ApiResult.Success(
                InquiryResponse(
                    inquiryId = "00000000-0000-4000-8000-000000000301",
                    inquiryCode = "INQ-REMOTE-001",
                    statusCode = "DRAFT",
                    stateVersion = 1,
                    idempotentReplay = createCalls > 1,
                    allowedActions = listOf(cancelAction()),
                )
            )
        }

        override suspend fun submit(
            inquiryId: String,
            stateVersion: Int,
            idempotencyKey: String,
        ): ApiResult<SubmitSymptomResponse> {
            submitCalls += 1
            submitKeys += idempotencyKey
            submittedStateVersions += stateVersion

            if (submitCalls <= failSubmitCount) {
                return ApiResult.Failure(
                    code = "NETWORK_ERROR",
                    message = "증상 제출 재시도 테스트 오류",
                    retryable = true,
                )
            }

            if (submitCalls <= staleConflictCount) {
                return ApiResult.Failure(
                    code = "STATE-CONFLICT-01",
                    message = "최신 상태를 반영해 다시 시도해 주세요.",
                    httpStatus = 409,
                    conflict = StateConflictSnapshot(
                        currentStatus = "DRAFT",
                        currentStateVersion = 2,
                        allowedActions = listOf(
                            AllowedAction(code = "SUBMIT_SYMPTOM")
                        ),
                    ),
                )
            }

            return ApiResult.Success(
                SubmitSymptomResponse(
                    inquiryId = inquiryId,
                    state = "QUESTIONNAIRE_IN_PROGRESS",
                    stateVersion = stateVersion + 1,
                    idempotentReplay = submitCalls > 1,
                    allowedActions = listOf(submitAnswersAction(), cancelAction()),
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

        private fun submitAnswersAction() = AllowedAction(
            code = "SUBMIT_ANSWERS",
            label = "추가 답변 제출",
            operationId = "submitFollowUpAnswers",
            style = "PRIMARY",
            requiresConfirmation = false,
        )

        private fun cancelAction() = AllowedAction(
            code = "CANCEL_INQUIRY",
            label = "문의 취소",
            operationId = "cancelInquiry",
            style = "DESTRUCTIVE",
            requiresConfirmation = true,
            confirmationMessage = "문의를 취소하시겠습니까?",
        )
    }

    private class FailingSubscriptionRepository : SubscriptionRepository {
        override suspend fun list(
            page: Int,
            size: Int,
        ): ApiResult<SubscriptionListDataDto> =
            ApiResult.Failure(
                code = "SUBSCRIPTION_REMOTE_FAILURE",
                message = "테스트용 구독 Remote 실패",
                retryable = true,
            )

        override suspend fun detail(
            subscriptionId: String,
        ): ApiResult<SubscriptionDetailDto> =
            error("이 테스트에서는 사용하지 않습니다.")
    }
}
