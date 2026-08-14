package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.RequestConsultationRequestDto
import com.skn29.watercare.core.model.RequestConsultationResult
import com.skn29.watercare.core.model.SubmitFollowUpAnswersRequestDto
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.model.toDomain
import com.skn29.watercare.core.model.toRequestDto
import com.skn29.watercare.core.network.WaterCareApi
import com.skn29.watercare.core.network.safeApiCall
import kotlinx.serialization.json.Json

interface CustomerInquiryRepository {
    suspend fun snapshot(inquiryId: String): ApiResult<CustomerInquirySnapshot>
    suspend fun guidance(inquiryId: String): ApiResult<GuidanceData> =
        ApiResult.Failure(
            code = "GUIDANCE_ROUTE_UNAVAILABLE",
            message = "안전 안내 조회 기능을 사용할 수 없습니다.",
            retryable = false,
        )
    suspend fun questions(inquiryId: String): ApiResult<CustomerInquiryQuestions>
    suspend fun submitAnswers(
        inquiryId: String,
        stateVersion: Int,
        answers: List<FollowUpAnswer>,
    ): ApiResult<SubmitFollowUpAnswersResult>
    suspend fun requestConsultation(
        inquiryId: String,
        stateVersion: Int,
    ): ApiResult<RequestConsultationResult> =
        ApiResult.Failure(
            code = "REQUEST_CONSULTATION_UNAVAILABLE",
            message = "상담 요청 기능을 사용할 수 없습니다.",
            retryable = false,
        )
}

class RemoteCustomerInquiryRepository(
    private val api: WaterCareApi,
    private val json: Json,
    private val idempotencyKeys: FollowUpIdempotencyKeyStore =
        FollowUpIdempotencyKeyStore(),
    private val consultationIdempotencyKeys:
        ConsultationRequestIdempotencyKeyStore =
        ConsultationRequestIdempotencyKeyStore(),
) : CustomerInquiryRepository {
    override suspend fun snapshot(
        inquiryId: String,
    ): ApiResult<CustomerInquirySnapshot> =
        safeApiCall(json) {
            api.customerInquirySnapshot(inquiryId.trim())
        }.mapSuccess { it.toDomain() }

    override suspend fun guidance(
        inquiryId: String,
    ): ApiResult<GuidanceData> {
        val normalizedInquiryId = inquiryId.trim()
        if (normalizedInquiryId.isEmpty()) {
            return ApiResult.Failure(
                code = "CLIENT_VALIDATION_ERROR",
                message = "문의 식별자를 확인해 주세요.",
                retryable = false,
            )
        }
        val result = safeApiCall(json) {
            api.customerInquiryGuidance(normalizedInquiryId)
        }.mapSuccess { it.toDomain() }
        return if (
            result is ApiResult.Failure &&
            result.httpStatus == 409 &&
            result.code == "AI_GUIDANCE_NOT_READY"
        ) {
            result.copy(
                message = "AI 안내를 준비하고 있습니다. 잠시 후 다시 확인해 주세요.",
                retryable = true,
            )
        } else {
            result
        }
    }

    override suspend fun questions(
        inquiryId: String,
    ): ApiResult<CustomerInquiryQuestions> =
        safeApiCall(json) {
            api.customerInquiryQuestions(inquiryId.trim())
        }.mapSuccess { it.toDomain() }

    override suspend fun submitAnswers(
        inquiryId: String,
        stateVersion: Int,
        answers: List<FollowUpAnswer>,
    ): ApiResult<SubmitFollowUpAnswersResult> {
        val normalizedAnswers = answers.map(FollowUpAnswer::normalized)
        if (
            inquiryId.isBlank() ||
            stateVersion < 1 ||
            normalizedAnswers.isEmpty() ||
            normalizedAnswers.size > 50 ||
            normalizedAnswers.any { !it.isValid } ||
            normalizedAnswers.map { it.questionId }.distinct().size != normalizedAnswers.size
        ) {
            return ApiResult.Failure(
                code = "CLIENT_VALIDATION_ERROR",
                message = "추가 답변 입력을 확인해 주세요.",
                retryable = false,
            )
        }

        val operation = FollowUpOperationIdentity(
            inquiryId = inquiryId.trim(),
            stateVersion = stateVersion,
            answers = normalizedAnswers,
        )
        val idempotencyKey = idempotencyKeys.keyFor(operation)
        val result = safeApiCall(json) {
            api.submitFollowUpAnswers(
                inquiryId = operation.inquiryId,
                idempotencyKey = idempotencyKey,
                body = SubmitFollowUpAnswersRequestDto(
                    stateVersion = stateVersion,
                    answers = normalizedAnswers.map { it.toRequestDto() },
                ),
            )
        }.mapSuccess { it.toDomain() }

        when (result) {
            is ApiResult.Success -> idempotencyKeys.complete(operation)
            is ApiResult.Failure -> {
                if (result.code == "DUPLICATE-EVENT-01") {
                    idempotencyKeys.abandon(operation)
                }
            }
        }
        return result
    }

    override suspend fun requestConsultation(
        inquiryId: String,
        stateVersion: Int,
    ): ApiResult<RequestConsultationResult> {
        val normalizedInquiryId = inquiryId.trim()

        if (
            normalizedInquiryId.isBlank() ||
            stateVersion < 1
        ) {
            return ApiResult.Failure(
                code = "CLIENT_VALIDATION_ERROR",
                message = "최신 문의 상태를 확인한 뒤 다시 시도해 주세요.",
                retryable = false,
            )
        }

        val operation =
            ConsultationRequestOperationIdentity(
                inquiryId = normalizedInquiryId,
                stateVersion = stateVersion,
            )

        val idempotencyKey =
            consultationIdempotencyKeys.keyFor(operation)

        val result = safeApiCall(json) {
            api.requestConsultation(
                inquiryId = operation.inquiryId,
                idempotencyKey = idempotencyKey,
                body = RequestConsultationRequestDto(
                    stateVersion = stateVersion,
                ),
            )
        }.mapSuccess { it.toDomain() }

        when (result) {
            is ApiResult.Success ->
                consultationIdempotencyKeys.complete(operation)

            is ApiResult.Failure -> {
                val preserveForSafeRetry =
                    result.retryable &&
                        result.conflict == null &&
                        result.code != "DUPLICATE-EVENT-01"

                if (!preserveForSafeRetry) {
                    consultationIdempotencyKeys.abandon(operation)
                }
            }
        }

        return result
    }
}

private inline fun <T, R> ApiResult<T>.mapSuccess(
    transform: (T) -> R,
): ApiResult<R> = when (this) {
    is ApiResult.Success -> ApiResult.Success(transform(value))
    is ApiResult.Failure -> this
}
