package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquiryQuestions
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.SubmitFollowUpAnswersRequestDto
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.model.toDomain
import com.skn29.watercare.core.model.toRequestDto
import com.skn29.watercare.core.network.WaterCareApi
import com.skn29.watercare.core.network.safeApiCall
import kotlinx.serialization.json.Json

interface CustomerInquiryRepository {
    suspend fun snapshot(inquiryId: String): ApiResult<CustomerInquirySnapshot>
    suspend fun questions(inquiryId: String): ApiResult<CustomerInquiryQuestions>
    suspend fun submitAnswers(
        inquiryId: String,
        stateVersion: Int,
        answers: List<FollowUpAnswer>,
    ): ApiResult<SubmitFollowUpAnswersResult>
}

class RemoteCustomerInquiryRepository(
    private val api: WaterCareApi,
    private val json: Json,
    private val idempotencyKeys: FollowUpIdempotencyKeyStore =
        FollowUpIdempotencyKeyStore(),
) : CustomerInquiryRepository {
    override suspend fun snapshot(
        inquiryId: String,
    ): ApiResult<CustomerInquirySnapshot> =
        safeApiCall(json) {
            api.customerInquirySnapshot(inquiryId.trim())
        }.mapSuccess { it.toDomain() }

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
}

private inline fun <T, R> ApiResult<T>.mapSuccess(
    transform: (T) -> R,
): ApiResult<R> = when (this) {
    is ApiResult.Success -> ApiResult.Success(transform(value))
    is ApiResult.Failure -> this
}
