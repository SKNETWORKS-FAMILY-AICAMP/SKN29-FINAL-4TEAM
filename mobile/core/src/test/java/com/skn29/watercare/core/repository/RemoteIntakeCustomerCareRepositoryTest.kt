package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
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
            customerInquiryRepository = StubCustomerInquiryRepository(),
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
            customerInquiryRepository = StubCustomerInquiryRepository(),
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
            customerInquiryRepository = StubCustomerInquiryRepository(),
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
    fun submitNotFound_retryCreatesFreshInquiryOperation() =
        runBlocking {
            val inquiryRepository =
                RecordingInquiryRepository(
                    submitResults =
                        mutableListOf(
                            ApiResult.Failure(
                                code =
                                    "RESOURCE_NOT_FOUND",
                                message =
                                    "inquiry not found",
                                httpStatus = 404,
                                retryable = false,
                            )
                        )
                )

            val repository =
                RemoteIntakeCustomerCareRepository(
                    inquiryRepository =
                        inquiryRepository,
                    subscriptionRepository =
                        FailingSubscriptionRepository(),
                    customerInquiryRepository =
                        StubCustomerInquiryRepository(),
                )

            val request = sampleRequest()

            val first =
                repository.submitIntake(request)

            val second =
                repository.submitIntake(request)

            assertTrue(
                first is ApiResult.Failure
            )
            assertTrue(
                second is ApiResult.Success<*>
            )

            assertEquals(
                2,
                inquiryRepository.createCalls,
            )
            assertEquals(
                2,
                inquiryRepository.submitCalls,
            )

            assertNotEquals(
                inquiryRepository.createKeys[0],
                inquiryRepository.createKeys[1],
            )

            assertNotEquals(
                inquiryRepository.submitKeys[0],
                inquiryRepository.submitKeys[1],
            )
        }

    @Test
    fun cancelledInquiry_retryCreatesFreshInquiryOperation() =
        runBlocking {
            val inquiryRepository =
                RecordingInquiryRepository(
                    submitResults =
                        mutableListOf(
                            ApiResult.Failure(
                                code =
                                    "STATE-CONFLICT-01",
                                message =
                                    "inquiry cancelled",
                                httpStatus = 409,
                                retryable = false,
                                conflict =
                                    StateConflictSnapshot(
                                        currentStatus =
                                            "CANCELLED",
                                        currentStateVersion =
                                            2,
                                        allowedActions =
                                            emptyList(),
                                    ),
                            )
                        )
                )

            val repository =
                RemoteIntakeCustomerCareRepository(
                    inquiryRepository =
                        inquiryRepository,
                    subscriptionRepository =
                        FailingSubscriptionRepository(),
                    customerInquiryRepository =
                        StubCustomerInquiryRepository(),
                )

            val request = sampleRequest()

            val first =
                repository.submitIntake(request)

            val second =
                repository.submitIntake(request)

            assertTrue(
                first is ApiResult.Failure
            )
            assertTrue(
                second is ApiResult.Success<*>
            )

            assertEquals(
                2,
                inquiryRepository.createCalls,
            )
            assertEquals(
                2,
                inquiryRepository.submitCalls,
            )

            assertNotEquals(
                inquiryRepository.createKeys[0],
                inquiryRepository.createKeys[1],
            )

            assertNotEquals(
                inquiryRepository.submitKeys[0],
                inquiryRepository.submitKeys[1],
            )
        }

    @Test
    fun guidance_delegatesToCustomerInquiryRepository_withoutFixtureFallback() = runBlocking {
        val guidanceRepository = StubCustomerInquiryRepository(
            guidanceResult = ApiResult.Success(sampleGuidance()),
        )
        val repository = RemoteIntakeCustomerCareRepository(
            inquiryRepository = RecordingInquiryRepository(),
            subscriptionRepository = FailingSubscriptionRepository(),
            customerInquiryRepository = guidanceRepository,
        )

        val result = repository.getGuidance(
            inquiryId = "00000000-0000-4000-8000-000000000301",
            scenario = MockScenario.NORMAL,
        )

        assertTrue(result is ApiResult.Success)
        val success = result as ApiResult.Success<GuidanceData>
        assertEquals("INQ-GUIDANCE-001", success.value.inquiryCode)
        assertEquals(
            listOf("00000000-0000-4000-8000-000000000301"),
            guidanceRepository.inquiryIds,
        )
    }

    @Test
    fun remoteHome_subscriptionFailureIsReturned_withoutFixtureFallback() = runBlocking {
        val repository = RemoteIntakeCustomerCareRepository(
            inquiryRepository = RecordingInquiryRepository(),
            subscriptionRepository = FailingSubscriptionRepository(),
            customerInquiryRepository = StubCustomerInquiryRepository(),
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

    private fun sampleGuidance() = GuidanceData(
        inquiryId = "00000000-0000-4000-8000-000000000301",
        inquiryCode = "INQ-GUIDANCE-001",
        statusCode = "AI_GUIDANCE",
        stateVersion = 3,
        symptomSummary = "누수 증상",
        riskLevel = "danger",
        usageGuidanceStatus = "TOTAL_STOP",
        usageGuidanceMessage = "즉시 사용을 중지하세요.",
        safeActions = listOf("전원에서 떨어진 안전한 곳에서 대기하세요."),
        escalationConditions = listOf("누수가 계속되면 상담을 요청하세요."),
        prohibitedActions = listOf("제품을 분해하지 마세요."),
        nextAction = "상담 요청",
        requiresConsultation = true,
        evidence = emptyList(),
        allowedActions = listOf(
            AllowedAction(code = "REQUEST_CONSULTATION")
        ),
    )

    private class RecordingInquiryRepository(
        private val failCreateCount: Int = 0,
        private val failSubmitCount: Int = 0,
        private val staleConflictCount: Int = 0,
        private val submitResults:
            MutableList<ApiResult<SubmitSymptomResponse>> =
                mutableListOf(),
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

            if (submitResults.isNotEmpty()) {
                return submitResults.removeAt(0)
            }

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

    private class StubCustomerInquiryRepository(
        private val guidanceResult: ApiResult<GuidanceData> =
            ApiResult.Failure(
                code = "GUIDANCE_ROUTE_UNAVAILABLE",
                message = "테스트 Guidance 미설정",
            ),
    ) : CustomerInquiryRepository {
        val inquiryIds = mutableListOf<String>()

        override suspend fun guidance(
            inquiryId: String,
        ): ApiResult<GuidanceData> {
            inquiryIds += inquiryId
            return guidanceResult
        }

        override suspend fun snapshot(
            inquiryId: String,
        ): ApiResult<CustomerInquirySnapshot> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun questions(
            inquiryId: String,
        ): ApiResult<CustomerInquiryQuestions> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun submitAnswers(
            inquiryId: String,
            stateVersion: Int,
            answers: List<FollowUpAnswer>,
        ): ApiResult<SubmitFollowUpAnswersResult> =
            error("이 테스트에서는 사용하지 않습니다.")
    }
}
