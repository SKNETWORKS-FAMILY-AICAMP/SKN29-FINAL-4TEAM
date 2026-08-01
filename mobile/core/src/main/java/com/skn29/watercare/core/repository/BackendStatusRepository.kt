package com.skn29.watercare.core.repository

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.network.WaterCareApi
import java.io.IOException

interface BackendStatusRepository {
    suspend fun health(): ApiResult<Unit>
}

class RemoteBackendStatusRepository(private val api: WaterCareApi) : BackendStatusRepository {
    override suspend fun health(): ApiResult<Unit> = try {
        val response = api.health()
        if (response.isSuccessful) ApiResult.Success(Unit) else ApiResult.Failure(
            code = "HTTP_${response.code()}",
            message = "Backend 상태 확인에 실패했습니다.",
            httpStatus = response.code(),
            retryable = response.code() >= 500,
        )
    } catch (exception: IOException) {
        ApiResult.Failure("NETWORK_ERROR", "Backend에 연결할 수 없습니다.", exception.message, retryable = true)
    } catch (exception: Exception) {
        ApiResult.Failure("CLIENT_ERROR", "Backend 상태 응답을 처리하지 못했습니다.", exception.message)
    }
}
