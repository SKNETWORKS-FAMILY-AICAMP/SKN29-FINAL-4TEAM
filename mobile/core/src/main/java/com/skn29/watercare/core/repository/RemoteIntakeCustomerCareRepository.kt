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
 * 4주차 부분 Remote 구현.
 *
 * 현재 Runtime에 공개된 구독 조회·문의 생성·증상 제출 API를 실제 Backend에 연결한다.
 * Guidance customer route가 공개되기 전에는 REMOTE에서 명시적으로 실패한다.
 * 합성 Guidance는 FAKE 또는 Offline Preview에서만 사용한다.
 */
class RemoteIntakeCustomerCareRepository(
    private val inquiryRepository: InquiryRepository,
    private val subscriptionRepository: SubscriptionRepository,
    private val customerInquiryRepository: CustomerInquiryRepository,
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
    ): ApiResult<GuidanceData> = customerInquiryRepository.guidance(inquiryId)

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
                val conflict =
                    submitResult.conflict

                val retryableDraftConflict =
                    conflict?.takeIf {
                        it.currentStatus == "DRAFT" &&
                            it.currentStateVersion != null &&
                            it.allowedActions.any { action ->
                                action.isRetrySubmitAction()
                            }
                    }

                if (retryableDraftConflict != null) {
                    synchronized(operationLock) {
                        if (
                            pendingOperations[fingerprint] ===
                            operation
                        ) {
                            operation.createdInquiry =
                                inquiry.copy(
                                    statusCode =
                                        retryableDraftConflict
                                            .currentStatus
                                            ?: inquiry.statusCode,
                                    stateVersion =
                                        retryableDraftConflict
                                            .currentStateVersion
                                            ?: inquiry.stateVersion,
                                    allowedActions =
                                        retryableDraftConflict
                                            .allowedActions,
                                )
                        }
                    }
                } else if (
                    submitResult
                        .invalidatesPendingInquiry()
                ) {
                    synchronized(operationLock) {
                        if (
                            pendingOperations[fingerprint] ===
                            operation
                        ) {
                            pendingOperations.remove(
                                fingerprint
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

    private fun ApiResult.Failure
        .invalidatesPendingInquiry(): Boolean {
        val currentStatus =
            conflict
                ?.currentStatus
                ?.trim()
                ?.uppercase()

        return (
            httpStatus == 404 ||
                httpStatus == 410 ||
                currentStatus == "CANCELLED" ||
                currentStatus == "RESOLVED"
        )
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
