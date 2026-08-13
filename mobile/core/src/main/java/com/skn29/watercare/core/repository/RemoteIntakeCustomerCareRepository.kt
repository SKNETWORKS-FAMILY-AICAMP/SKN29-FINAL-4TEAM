package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomIntakeRequest
import com.skn29.watercare.core.model.toCustomerHomeData
import java.util.UUID

/**
 * 5주차 P0 고객 Mobile Remote 구현.
 *
 * 현재 Runtime에 공개된 구독 조회·문의 생성·증상 제출·Guidance API를
 * 실제 Backend에 연결한다. Remote 실패를 합성 Guidance로 대체하지 않는다.
 */
class RemoteIntakeCustomerCareRepository(
    private val inquiryRepository: InquiryRepository,
    private val subscriptionRepository: SubscriptionRepository,
    private val customerInquiryRepository: CustomerInquiryRepository? = null,
) : CustomerCareRepository {
    private data class PendingIntakeOperation(
        val createIdempotencyKey: String,
        val submitIdempotencyKey: String,
        var createdInquiry: InquiryResponse? = null,
    )

    private val operationLock = Any()
    private val pendingOperations = mutableMapOf<String, PendingIntakeOperation>()

    override suspend fun getHome(): ApiResult<CustomerHomeData> =
        when (val result = subscriptionRepository.list()) {
            is ApiResult.Failure -> result
            is ApiResult.Success -> {
                val selected = result.value.items.firstOrNull()
                    ?: return ApiResult.Failure(
                        code = "SUBSCRIPTION_EMPTY",
                        message = "현재 문의를 시작할 수 있는 구독이 없습니다.",
                    )
                ApiResult.Success(selected.toCustomerHomeData())
            }
        }

    override suspend fun getGuidance(
        inquiryId: String,
        scenario: MockScenario,
    ): ApiResult<GuidanceData> {
        val remote = customerInquiryRepository
            ?: return ApiResult.Failure(
                code = "GUIDANCE_REPOSITORY_UNAVAILABLE",
                message = "안전 안내 조회 기능을 사용할 수 없습니다.",
                retryable = false,
            )
        return remote.guidance(inquiryId)
    }

    override suspend fun submitIntake(
        request: SymptomIntakeRequest,
    ): ApiResult<IntakeSubmission> {
        val fingerprint = request.fingerprint()
        val operation = synchronized(operationLock) {
            pendingOperations.getOrPut(fingerprint) {
                PendingIntakeOperation(
                    createIdempotencyKey = UUID.randomUUID().toString(),
                    submitIdempotencyKey = UUID.randomUUID().toString(),
                )
            }
        }

        val inquiry = operation.createdInquiry ?: when (
            val createResult = inquiryRepository.create(
                request = CreateInquiryRequest(
                    subscriptionId = request.subscriptionId,
                    channelCode = "MOBILE",
                    rawText = request.toBackendRawText(),
                    representativeSymptomCode = request.symptomCodes.firstOrNull(),
                    questionnaireSessionId = null,
                ),
                idempotencyKey = operation.createIdempotencyKey,
            )
        ) {
            is ApiResult.Failure -> return createResult
            is ApiResult.Success -> {
                synchronized(operationLock) {
                    operation.createdInquiry = createResult.value
                }
                createResult.value
            }
        }

        return when (
            val submitResult = inquiryRepository.submit(
                inquiryId = inquiry.inquiryId,
                stateVersion = inquiry.stateVersion,
                idempotencyKey = operation.submitIdempotencyKey,
            )
        ) {
            is ApiResult.Failure -> {
                submitResult.conflict
                    ?.takeIf { conflict ->
                        conflict.currentStatus == "DRAFT" &&
                            conflict.currentStateVersion != null &&
                            conflict.allowedActions.any { it.isRetrySubmitAction() }
                    }
                    ?.let { conflict ->
                        synchronized(operationLock) {
                            if (pendingOperations[fingerprint] === operation) {
                                operation.createdInquiry = inquiry.copy(
                                    statusCode = conflict.currentStatus ?: inquiry.statusCode,
                                    stateVersion = conflict.currentStateVersion
                                        ?: inquiry.stateVersion,
                                    allowedActions = conflict.allowedActions,
                                )
                            }
                        }
                    }
                submitResult
            }

            is ApiResult.Success -> {
                synchronized(operationLock) {
                    if (pendingOperations[fingerprint] === operation) {
                        pendingOperations.remove(fingerprint)
                    }
                }
                ApiResult.Success(
                    IntakeSubmission(
                        inquiryId = submitResult.value.inquiryId,
                        inquiryCode = inquiry.inquiryCode,
                        guidanceScenario = MockScenario.BACKEND_PROCESSING.name,
                        statusCode = submitResult.value.state,
                        stateVersion = submitResult.value.stateVersion,
                        allowedActions = submitResult.value.allowedActions,
                        idempotentReplay = submitResult.value.idempotentReplay,
                    )
                )
            }
        }
    }

    private fun SymptomIntakeRequest.fingerprint(): String = listOf(
        subscriptionId,
        symptomCodes.sorted().joinToString(","),
        rawText.trim(),
        occurrenceCondition.orEmpty().trim(),
        displayText.orEmpty().trim(),
        entryMode,
    ).joinToString(separator = "\u001F")

    private fun SymptomIntakeRequest.toBackendRawText(): String = buildList {
        rawText.trim().takeIf(String::isNotEmpty)?.let(::add)
        occurrenceCondition
            ?.trim()
            ?.takeIf(String::isNotEmpty)
            ?.let { add("발생 조건: $it") }
        displayText
            ?.trim()
            ?.takeIf(String::isNotEmpty)
            ?.let { add("제품 표시 문구·오류 코드: $it") }
    }.joinToString(separator = "\n")
}
