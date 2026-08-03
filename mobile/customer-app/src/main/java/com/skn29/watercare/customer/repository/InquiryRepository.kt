package com.skn29.watercare.customer.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CancelInquiryRequest
import com.skn29.watercare.core.model.CancelInquiryResponse
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.InquiryResponse
import com.skn29.watercare.core.network.safeApiCall
import com.skn29.watercare.customer.data.watercare.CustomerInquiryApi
import com.skn29.watercare.customer.data.watercare.InquirySessionStore
import kotlinx.serialization.json.Json

interface InquiryRepository {
    suspend fun create(
        request: CreateInquiryRequest,
        idempotencyKey: String,
    ): ApiResult<InquiryResponse>

    suspend fun cancel(
        inquiryId: String,
        stateVersion: Int,
        reasonCode: String,
        reasonDetail: String?,
        idempotencyKey: String,
    ): ApiResult<CancelInquiryResponse>
}

class RemoteInquiryRepository(
    private val api: CustomerInquiryApi,
    private val json: Json,
    private val sessionStore: InquirySessionStore,
) : InquiryRepository {
    override suspend fun create(
        request: CreateInquiryRequest,
        idempotencyKey: String,
    ): ApiResult<InquiryResponse> {
        val result: ApiResult<InquiryResponse> = safeApiCall(json) {
            api.createInquiry(idempotencyKey, request)
        }
        when (result) {
            is ApiResult.Success -> sessionStore.saveCreated(
                response = result.value,
                correlationId = result.metadata?.correlationId,
            )
            is ApiResult.Failure -> result.conflict?.let {
                sessionStore.applyConflict(it, result.correlationId)
            }
        }
        return result
    }

    override suspend fun cancel(
        inquiryId: String,
        stateVersion: Int,
        reasonCode: String,
        reasonDetail: String?,
        idempotencyKey: String,
    ): ApiResult<CancelInquiryResponse> {
        val result: ApiResult<CancelInquiryResponse> = safeApiCall(json) {
            api.cancelInquiry(
                inquiryId = inquiryId,
                idempotencyKey = idempotencyKey,
                body = CancelInquiryRequest(stateVersion, reasonCode, reasonDetail),
            )
        }
        when (result) {
            is ApiResult.Success -> sessionStore.saveCancelled(
                response = result.value,
                correlationId = result.metadata?.correlationId,
            )
            is ApiResult.Failure -> result.conflict?.let {
                sessionStore.applyConflict(it, result.correlationId)
            }
        }
        return result
    }
}
