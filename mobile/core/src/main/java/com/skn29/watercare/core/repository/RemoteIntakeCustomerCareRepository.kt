package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomIntakeRequest
import java.util.UUID

/**
 * 4주차 부분 Remote 구현.
 *
 * 현재 Runtime에 공개된 문의 생성 API만 실제 Backend에 연결하고,
 * 제품·구독 홈과 AI 안내는 계약된 Endpoint가 제공될 때까지 명시적 Fixture에 위임한다.
 * Remote 실패를 Fixture 성공으로 자동 변환하지 않는다.
 */
class RemoteIntakeCustomerCareRepository(
    private val inquiryRepository: InquiryRepository,
    private val fallbackRepository: CustomerCareRepository,
) : CustomerCareRepository {
    private val keyLock = Any()
    private val pendingIdempotencyKeys = mutableMapOf<String, String>()

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
        val idempotencyKey = synchronized(keyLock) {
            pendingIdempotencyKeys.getOrPut(fingerprint) { UUID.randomUUID().toString() }
        }

        val createRequest = CreateInquiryRequest(
            subscriptionId = request.subscriptionId,
            rawText = request.toBackendRawText(),
            representativeSymptomCode = request.symptomCodes.firstOrNull(),
            questionnaireSessionId = null,
        )

        return when (
            val result = inquiryRepository.create(
                request = createRequest,
                idempotencyKey = idempotencyKey,
            )
        ) {
            is ApiResult.Success -> {
                synchronized(keyLock) {
                    pendingIdempotencyKeys.remove(fingerprint)
                }
                ApiResult.Success(
                    IntakeSubmission(
                        inquiryId = result.value.inquiryId,
                        inquiryCode = result.value.inquiryCode,
                        guidanceScenario = MockScenario.BACKEND_PROCESSING.name,
                        statusCode = result.value.statusCode,
                        stateVersion = result.value.stateVersion,
                        allowedActions = result.value.allowedActions,
                    )
                )
            }
            is ApiResult.Failure -> result
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
