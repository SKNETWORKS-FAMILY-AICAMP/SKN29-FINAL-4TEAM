package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomIntakeRequest
import java.util.UUID

/**
 * 4주차 부분 Remote 구현.
 *
 * 현재 Runtime에 공개된 문의 생성·증상 제출 API를 실제 Backend에 연결하고,
 * 제품·구독 홈과 AI 안내는 계약된 Endpoint가 제공될 때까지 명시적 Fixture에 위임한다.
 * Remote 실패를 Fixture 성공으로 자동 변환하지 않는다.
 */
class RemoteIntakeCustomerCareRepository(
    private val inquiryRepository: InquiryRepository,
    private val fallbackRepository: CustomerCareRepository,
) : CustomerCareRepository {
    private data class PendingIntakeOperation(
        val createIdempotencyKey: String,
        val submitIdempotencyKey: String,
        var createdInquiry: InquiryResponse? = null,
    )

    private val operationLock = Any()
    private val pendingOperations = mutableMapOf<String, PendingIntakeOperation>()

    override suspend fun getHome(): ApiResult<CustomerHomeData> =
        fallbackRepository.getHome()

    override suspend fun getGuidance(
        inquiryId: String,
        scenario: MockScenario,
    ): ApiResult<GuidanceData> =
        fallbackRepository.getGuidance(inquiryId, scenario)

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
