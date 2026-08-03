package com.skn29.watercare.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class ApiEnvelope<T>(
    val success: Boolean,
    val data: T? = null,
    val error: ApiErrorPayload? = null,
    val metadata: ResponseMetadata? = null,
)

@Serializable
data class ApiErrorPayload(
    val code: String,
    val message: String,
    val details: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class ResponseMetadata(
    @SerialName("correlation_id") val correlationId: String? = null,
)

data class StateConflictSnapshot(
    val currentStatus: String?,
    val currentStateVersion: Int?,
    val allowedActions: List<RuntimeAllowedAction>,
)

sealed interface ApiResult<out T> {
    data class Success<T>(
        val value: T,
        val metadata: ResponseMetadata? = null,
    ) : ApiResult<T>

    data class Failure(
        val code: String,
        val message: String,
        val details: String? = null,
        val httpStatus: Int? = null,
        val retryable: Boolean = false,
        val conflict: StateConflictSnapshot? = null,
        val fieldErrors: Map<String, List<String>> = emptyMap(),
        val correlationId: String? = null,
    ) : ApiResult<Nothing>
}
