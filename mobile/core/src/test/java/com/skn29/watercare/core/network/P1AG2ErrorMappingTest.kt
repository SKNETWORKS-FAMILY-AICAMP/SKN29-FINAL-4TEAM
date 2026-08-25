package com.skn29.watercare.core.network

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.SessionResponse
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class P1AG2ErrorMappingTest {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    @Test
    fun validation422_mapsDetailsFieldsToFieldErrors() = runBlocking {
        val body = """
            {
              "success": false,
              "data": null,
              "error": {
                "code": "VALIDATION_ERROR",
                "message": "입력값을 확인해 주세요.",
                "details": {
                  "fields": {
                    "username": ["아이디 형식을 확인해 주세요."],
                    "password": ["비밀번호는 12자 이상이어야 합니다."]
                  }
                }
              }
            }
        """.trimIndent()

        val result = safeApiCall<SessionResponse>(json) {
            Response.error(
                422,
                body.toResponseBody(),
            )
        }

        assertTrue(result is ApiResult.Failure)

        val failure = result as ApiResult.Failure

        assertEquals(422, failure.httpStatus)
        assertEquals(
            listOf("아이디 형식을 확인해 주세요."),
            failure.fieldErrors["username"],
        )
        assertEquals(
            listOf("비밀번호는 12자 이상이어야 합니다."),
            failure.fieldErrors["password"],
        )
        assertFalse(failure.retryable)
    }

    @Test
    fun rateLimit429_mapsRetryAfterSecondsFromBody() = runBlocking {
        val body = """
            {
              "success": false,
              "data": null,
              "error": {
                "code": "RATE_LIMITED",
                "message": "잠시 후 다시 시도해 주세요.",
                "details": {
                  "retry_after_seconds": 60
                }
              }
            }
        """.trimIndent()

        val result = safeApiCall<SessionResponse>(json) {
            Response.error(
                429,
                body.toResponseBody(),
            )
        }

        assertTrue(result is ApiResult.Failure)

        val failure = result as ApiResult.Failure

        assertEquals(429, failure.httpStatus)
        assertTrue(failure.retryable)
        assertEquals(60, failure.retryAfterSeconds)
    }

    @Test
    fun rateLimit429_prefersRetryAfterHeaderOverBody() = runBlocking {
        val body = """
            {
              "success": false,
              "data": null,
              "error": {
                "code": "RATE_LIMITED",
                "message": "잠시 후 다시 시도해 주세요.",
                "details": {
                  "retry_after_seconds": 60
                }
              }
            }
        """.trimIndent()

        val rawResponse = okhttp3.Response.Builder()
            .request(
                Request.Builder()
                    .url("http://localhost/api/v1/auth/login")
                    .build()
            )
            .protocol(Protocol.HTTP_1_1)
            .code(429)
            .message("Too Many Requests")
            .header("Retry-After", "30")
            .build()

        val result = safeApiCall<SessionResponse>(json) {
            Response.error(
                body.toResponseBody(),
                rawResponse,
            )
        }

        assertTrue(result is ApiResult.Failure)

        val failure = result as ApiResult.Failure

        assertEquals(429, failure.httpStatus)
        assertTrue(failure.retryable)
        assertEquals(30, failure.retryAfterSeconds)
    }
    @Test
    fun authVerification401_preservesBackendUserMessage() =
        runBlocking {
            val message =
                "인증정보를 확인할 수 없습니다. 처음부터 다시 시도해 주세요."

            val body =
                """
                {
                  "success": false,
                  "data": null,
                  "error": {
                    "code": "AUTH_VERIFICATION_FAILED",
                    "message": "$message",
                    "details": {}
                  }
                }
                """.trimIndent()

            val result =
                safeApiCall<SessionResponse>(
                    json
                ) {
                    Response.error(
                        401,
                        body.toResponseBody(),
                    )
                }

            assertTrue(
                result is ApiResult.Failure
            )

            val failure =
                result as ApiResult.Failure

            assertEquals(
                "AUTH_VERIFICATION_FAILED",
                failure.code,
            )
            assertEquals(
                message,
                failure.message,
            )
            assertEquals(
                401,
                failure.httpStatus,
            )
        }

    @Test
    fun identifierUnavailable409_preservesBackendUserMessage() =
        runBlocking {
            val message =
                "사용할 수 없는 아이디입니다. 다른 아이디를 입력해 주세요."

            val body =
                """
                {
                  "success": false,
                  "data": null,
                  "error": {
                    "code": "AUTH_IDENTIFIER_UNAVAILABLE",
                    "message": "$message",
                    "details": {}
                  }
                }
                """.trimIndent()

            val result =
                safeApiCall<SessionResponse>(
                    json
                ) {
                    Response.error(
                        409,
                        body.toResponseBody(),
                    )
                }

            assertTrue(
                result is ApiResult.Failure
            )

            val failure =
                result as ApiResult.Failure

            assertEquals(
                "AUTH_IDENTIFIER_UNAVAILABLE",
                failure.code,
            )
            assertEquals(
                message,
                failure.message,
            )
            assertEquals(
                409,
                failure.httpStatus,
            )
        }

    @Test
    fun nonAuth401_stillUsesSessionExpiredMessage() =
        runBlocking {
            val body =
                """
                {
                  "success": false,
                  "data": null,
                  "error": {
                    "code": "RESOURCE_UNAUTHORIZED",
                    "message": "internal detail",
                    "details": {}
                  }
                }
                """.trimIndent()

            val result =
                safeApiCall<SessionResponse>(
                    json
                ) {
                    Response.error(
                        401,
                        body.toResponseBody(),
                    )
                }

            assertTrue(
                result is ApiResult.Failure
            )

            val failure =
                result as ApiResult.Failure

            assertEquals(
                401,
                failure.httpStatus,
            )

            assertTrue(
                failure.message.isNotBlank()
            )

            assertTrue(
                failure.message !=
                    "internal detail"
            )
        }

}