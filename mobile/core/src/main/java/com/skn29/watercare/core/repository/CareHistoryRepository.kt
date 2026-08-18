package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CareHistoryCreateRequestDto
import com.skn29.watercare.core.model.CareHistoryItemDto
import com.skn29.watercare.core.model.CareHistoryListDataDto
import com.skn29.watercare.core.model.CareHistoryMutationResultDto
import com.skn29.watercare.core.network.WaterCareApi
import com.skn29.watercare.core.network.safeApiCall
import java.util.UUID
import kotlinx.serialization.json.Json

data class CareHistoryOperationIdentity(
    val subscriptionId: String,
    val careTypeCode: String,
    val performedOn: String,
)

class CareHistoryIdempotencyKeyStore(
    private val createKey: () -> String = {
        UUID.randomUUID().toString()
    },
) {
    private val lock = Any()
    private val pending =
        mutableMapOf<CareHistoryOperationIdentity, String>()

    fun keyFor(
        operation: CareHistoryOperationIdentity,
    ): String = synchronized(lock) {
        pending.getOrPut(operation, createKey)
    }

    fun complete(
        operation: CareHistoryOperationIdentity,
    ) {
        synchronized(lock) {
            pending.remove(operation)
        }
    }

    fun abandon(
        operation: CareHistoryOperationIdentity,
    ) {
        synchronized(lock) {
            pending.remove(operation)
        }
    }
}

interface CareHistoryRepository {
    suspend fun list(
        subscriptionId: String,
        page: Int = 1,
        size: Int = 20,
    ): ApiResult<CareHistoryListDataDto>

    suspend fun detail(
        subscriptionId: String,
        careRecordId: String,
    ): ApiResult<CareHistoryItemDto>

    suspend fun create(
        subscriptionId: String,
        request: CareHistoryCreateRequestDto,
        idempotencyKeyOverride: String? = null,
    ): ApiResult<CareHistoryMutationResultDto>
}

class RemoteCareHistoryRepository(
    private val api: WaterCareApi,
    private val json: Json,
    private val idempotencyKeys: CareHistoryIdempotencyKeyStore =
        CareHistoryIdempotencyKeyStore(),
) : CareHistoryRepository {
    override suspend fun list(
        subscriptionId: String,
        page: Int,
        size: Int,
    ): ApiResult<CareHistoryListDataDto> =
        safeApiCall(json) {
            api.myCareRecords(
                subscriptionId = subscriptionId,
                page = page,
                size = size,
            )
        }

    override suspend fun detail(
        subscriptionId: String,
        careRecordId: String,
    ): ApiResult<CareHistoryItemDto> =
        safeApiCall(json) {
            api.myCareRecord(
                subscriptionId = subscriptionId,
                careRecordId = careRecordId,
            )
        }

    override suspend fun create(
        subscriptionId: String,
        request: CareHistoryCreateRequestDto,
        idempotencyKeyOverride: String?,
    ): ApiResult<CareHistoryMutationResultDto> {
        val operation = CareHistoryOperationIdentity(
            subscriptionId = subscriptionId,
            careTypeCode = request.careTypeCode,
            performedOn = request.performedOn,
        )
        val managedKey = idempotencyKeyOverride == null
        val idempotencyKey =
            idempotencyKeyOverride
                ?: idempotencyKeys.keyFor(operation)

        val result = safeApiCall(json) {
            api.createMyCareRecord(
                subscriptionId = subscriptionId,
                idempotencyKey = idempotencyKey,
                body = request,
            )
        }

        if (managedKey) {
            when (result) {
                is ApiResult.Success -> {
                    idempotencyKeys.complete(operation)
                }

                is ApiResult.Failure -> {
                    val keepForSafeReplay =
                        result.retryable ||
                            result.httpStatus == 401 ||
                            result.code == "NETWORK_ERROR"

                    if (!keepForSafeReplay) {
                        idempotencyKeys.abandon(operation)
                    }
                }
            }
        }

        return result
    }
}