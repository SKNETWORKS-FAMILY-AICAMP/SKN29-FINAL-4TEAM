package com.skn29.watercare.core.network

import android.content.Context
import com.skn29.watercare.core.auth.TokenStore
import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.ResponseMetadata
import com.skn29.watercare.core.model.RuntimeAllowedAction
import com.skn29.watercare.core.model.StateConflictSnapshot
import com.skn29.watercare.core.model.toCodeOnlyRuntimeAction
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
import kotlinx.serialization.json.jsonPrimitive
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
                    redactHeader("Idempotency-Key")
                })
            }
        }
        .build()

    private val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(normalizeBaseUrl(baseUrl))
        .client(mainClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    val api: WaterCareApi = createService(WaterCareApi::class.java)

    fun <T> createService(serviceClass: Class<T>): T = retrofit.create(serviceClass)

    private fun normalizeBaseUrl(value: String): String =
        if (value.endsWith('/')) value else "$value/"
}

suspend fun <T> safeApiCall(
    json: Json,
    call: suspend () -> Response<ApiEnvelope<T>>,
): ApiResult<T> = try {
    val response = call()
    val body = response.body()
    val headerCorrelationId = response.headers()[CorrelationIdInterceptor.CORRELATION_HEADER]
    val successMetadata = body?.metadata
        ?: headerCorrelationId?.let(::ResponseMetadata)
    val successData = body?.data
    if (response.isSuccessful && body?.success == true && successData != null) {
        ApiResult.Success(successData, successMetadata)
    } else {
        val parsed = response.errorBody()?.string()?.takeIf(String::isNotBlank)?.let { raw ->
            runCatching {
                json.decodeFromString<ApiEnvelope<JsonElement>>(raw)
            }.getOrNull()
        }
        val error = body?.error ?: parsed?.error
        val metadata = body?.metadata
            ?: parsed?.metadata
            ?: headerCorrelationId?.let(::ResponseMetadata)
        val status = response.code()
        ApiResult.Failure(
            code = error?.code ?: "HTTP_$status",
            message = ApiErrorMapper.userMessage(status, error?.code, error?.message),
            details = error?.details?.toString(),
            httpStatus = status,
            retryable = status == 408 || status == 429 || status >= 500,
            conflict = if (status == 409) extractConflict(error?.details, parsed?.data) else null,
            fieldErrors = if (status == 422) extractFieldErrors(error?.details) else emptyMap(),
            correlationId = metadata?.correlationId,
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
    val status = current["current_status"]?.jsonPrimitive?.contentOrNull
        ?: current["status"]?.jsonPrimitive?.contentOrNull
    val version = current["current_state_version"]?.jsonPrimitive?.intOrNull
        ?: current["state_version"]?.jsonPrimitive?.intOrNull
    val actions = (current["allowed_actions"] as? JsonArray)
        ?.mapNotNull(::parseRuntimeAllowedAction)
        .orEmpty()
    if (status == null && version == null && actions.isEmpty()) null
    else StateConflictSnapshot(status, version, actions)
}.getOrNull()

internal fun parseRuntimeAllowedAction(element: JsonElement): RuntimeAllowedAction? {
    return when (element) {
        is JsonObject -> {
            val code = element["code"]?.jsonPrimitive?.contentOrNull
            if (code == null) {
                null
            } else {
                val label = element["label"]?.jsonPrimitive?.contentOrNull
                val operationId = element["operation_id"]?.jsonPrimitive?.contentOrNull
                val style = element["style"]?.jsonPrimitive?.contentOrNull
                val requiresConfirmation = element["requires_confirmation"]
                    ?.jsonPrimitive
                    ?.booleanOrNull
                val completeObject =
                    label != null && operationId != null && style != null && requiresConfirmation != null
                RuntimeAllowedAction(
                    code = code,
                    label = label,
                    operationId = operationId,
                    style = style,
                    requiresConfirmation = requiresConfirmation ?: false,
                    confirmationMessage = element["confirmation_message"]
                        ?.jsonPrimitive
                        ?.contentOrNull,
                    objectContractAvailable = completeObject,
                )
            }
        }
        is JsonPrimitive -> element.contentOrNull
            ?.takeIf(String::isNotBlank)
            ?.toCodeOnlyRuntimeAction()
        else -> null
    }
}

internal fun extractFieldErrors(details: Map<String, JsonElement>?): Map<String, List<String>> =
    details.orEmpty().mapValues { (_, element) ->
        when (element) {
            is JsonArray -> element.mapNotNull { item ->
                (item as? JsonPrimitive)?.contentOrNull
            }
            is JsonPrimitive -> listOfNotNull(element.contentOrNull)
            else -> listOf(element.toString())
        }
    }
