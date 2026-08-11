package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.SubscriptionDetailDto
import com.skn29.watercare.core.model.SubscriptionListDataDto
import com.skn29.watercare.core.network.WaterCareApi
import com.skn29.watercare.core.network.safeApiCall
import kotlinx.serialization.json.Json

interface SubscriptionRepository {
    suspend fun list(page: Int = 1, size: Int = 20): ApiResult<SubscriptionListDataDto>
    suspend fun detail(subscriptionId: String): ApiResult<SubscriptionDetailDto>
}

class RemoteSubscriptionRepository(
    private val api: WaterCareApi,
    private val json: Json,
) : SubscriptionRepository {
    override suspend fun list(
        page: Int,
        size: Int,
    ): ApiResult<SubscriptionListDataDto> =
        safeApiCall(json) { api.mySubscriptions(page = page, size = size) }

    override suspend fun detail(
        subscriptionId: String,
    ): ApiResult<SubscriptionDetailDto> =
        safeApiCall(json) { api.mySubscription(subscriptionId = subscriptionId) }
}
