package com.skn29.watercare.core.network

import android.content.Context
import com.skn29.watercare.core.auth.TokenStore
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.StateConflictSnapshot
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class NetworkFactory(
    context: Context,
    baseUrl: String,
    debug: Boolean,
) {
    val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        isLenient = false
    }
    val tokenStore = TokenStore(context)

    private val refreshClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .addInterceptor(CorrelationIdInterceptor())
        .build()

    private val refreshApi = Retrofit.Builder()
        .baseUrl(normalizeBaseUrl(baseUrl))
        .client(refreshClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(RefreshApi::class.java)

    private val mainClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(25, TimeUnit.SECONDS)
        .writeTimeout(25, TimeUnit.SECONDS)
        .addInterceptor(CorrelationIdInterceptor())
        .addInterceptor(AuthInterceptor(tokenStore))
        .authenticator(TokenAuthenticator(tokenStore, refreshApi))
        .apply {
            if (debug) {
                addInterceptor(HttpLoggingInterceptor().apply {
                    level = HttpLoggingInterceptor.Level.BASIC
                    redactHeader("Authorization")
                    redactHeader("Cookie")
                })
            }
        }
        .build()

    val api: WaterCareApi = Retrofit.Builder()
        .baseUrl(normalizeBaseUrl(baseUrl))
        .client(mainClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(WaterCareApi::class.java)

    private fun normalizeBaseUrl(value: String): String =
        if (value.endsWith('/')) value else "$value/"
}

suspend fun <T> safeApiCall(
    json: Json,
    call: suspend () -> Response<ApiEnvelope<T>>,
): ApiResult<T> = try {
    val response = call()
    val body = response.body()
    val successData = body?.data
    if (response.isSuccessful && body?.success == true && successData != null) {
        ApiResult.Success(successData)
    } else {
        val parsed = response.errorBody()
            ?.string()
            ?.takeIf(String::isNotBlank)
            ?.let { raw ->
                runCatching {
                    json.decodeFromString<ApiEnvelope<JsonElement>>(raw)
                }.getOrNull()
            }
        val error = body?.error ?: parsed?.error
        val status = response.code()

        val retryAfterSeconds =
            response.headers()["Retry-After"]
                ?.trim()
                ?.toIntOrNull()
                ?: (error?.details?.get("retry_after_seconds") as? JsonPrimitive)
                    ?.intOrNull

        ApiResult.Failure(
            code = error?.code ?: "HTTP_$status",
            message = ApiErrorMapper.userMessage(status, error?.message),
            details = error?.details?.toString(),
            httpStatus = status,
            retryable = status == 408 || status == 429 || status >= 500,
            conflict = if (status == 409) {
                extractConflict(error?.details, parsed?.data)
            } else {
                null
            },
            fieldErrors = if (status == 422) {
                extractFieldErrors(error?.details)
            } else {
                emptyMap()
            },
            retryAfterSeconds = if (status == 429) {
                retryAfterSeconds
            } else {
                null
            },
        )
    }
} catch (exception: IOException) {
    ApiResult.Failure(
        code = "NETWORK_ERROR",
        message = "서버에 연결할 수 없습니다. 네트워크와 Backend 실행 상태를 확인해 주세요.",
        details = exception.message,
        retryable = true,
    )
} catch (exception: Exception) {
    ApiResult.Failure(
        code = "CLIENT_PARSE_ERROR",
        message = "응답을 안전하게 처리하지 못했습니다. 다시 시도하거나 상담을 이용해 주세요.",
        details = exception.message,
    )
}

internal fun extractFieldErrors(
    details: Map<String, JsonElement>?,
): Map<String, List<String>> {
    if (details == null) return emptyMap()

    val fields =
        (details["fields"] as? JsonObject)
            ?: JsonObject(details)

    return fields
        .mapValues { (_, value) ->
            when (value) {
                is JsonArray -> value.mapNotNull { item ->
                    (item as? JsonPrimitive)
                        ?.contentOrNull
                        ?.trim()
                        ?.takeIf(String::isNotEmpty)
                }

                is JsonPrimitive -> listOfNotNull(
                    value.contentOrNull
                        ?.trim()
                        ?.takeIf(String::isNotEmpty)
                )

                else -> emptyList()
            }
        }
        .filterValues { errors -> errors.isNotEmpty() }
}

internal fun extractConflict(
    details: Map<String, JsonElement>?,
    data: JsonElement?,
): StateConflictSnapshot? = runCatching {
    val root: JsonObject? = when {
        data is JsonObject -> data
        details != null -> JsonObject(details)
        else -> null
    }
    if (root == null) return@runCatching null

    val current = (root["current"] as? JsonObject) ?: root
    val status = current.stringValue("current_status")
        ?: current.stringValue("status")
    val version = current.intValue("current_state_version")
        ?: current.intValue("state_version")
    val actions = (current["allowed_actions"] as? JsonArray)
        ?.mapNotNull(JsonElement::toAllowedActionOrNull)
        .orEmpty()

    if (status == null && version == null && actions.isEmpty()) {
        null
    } else {
        StateConflictSnapshot(
            currentStatus = status,
            currentStateVersion = version,
            allowedActions = actions,
        )
    }
}.getOrNull()

private fun JsonElement.toAllowedActionOrNull(): AllowedAction? = when (this) {
    is JsonObject -> {
        val actionCode = stringValue("code")
            ?.trim()
            ?.takeIf(String::isNotEmpty)
            ?: return null

        AllowedAction(
            code = actionCode,
            label = stringValue("label").orEmpty(),
            operationId = stringValue("operation_id").orEmpty(),
            style = stringValue("style").orEmpty().ifBlank { "UNKNOWN" },
            requiresConfirmation = booleanValue("requires_confirmation") ?: false,
            confirmationMessage = stringValue("confirmation_message"),
        )
    }

    is JsonPrimitive -> takeIf { isString }
        ?.contentOrNull
        ?.trim()
        ?.takeIf(String::isNotEmpty)
        ?.let { code -> AllowedAction(code = code) }

    else -> null
}

private fun JsonObject.stringValue(name: String): String? =
    (get(name) as? JsonPrimitive)
        ?.takeIf { it.isString }
        ?.contentOrNull

private fun JsonObject.intValue(name: String): Int? =
    (get(name) as? JsonPrimitive)?.intOrNull

private fun JsonObject.booleanValue(name: String): Boolean? =
    (get(name) as? JsonPrimitive)?.booleanOrNull
