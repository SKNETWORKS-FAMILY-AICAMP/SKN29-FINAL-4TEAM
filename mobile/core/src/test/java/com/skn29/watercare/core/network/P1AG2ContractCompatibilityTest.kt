package com.skn29.watercare.core.network

import com.skn29.watercare.core.model.ApiEnvelope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.SessionResponse
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class P1AG2ContractCompatibilityTest {

    private val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    @Test
    fun loginResponse_canBeDecodedByCurrentSessionResponse() {
        val raw = """
            {
              "success": true,
              "data": {
                "access_token": "access.jwt",
                "refresh_token": "refresh.jwt",
                "token_type": "Bearer",
                "access_expires_in": 3600,
                "refresh_expires_in": 604800,
                "user": {
                  "id": "00000000-0000-0000-0000-000000000001",
                  "display_name": "합성 고객",
                  "role_code": "CUSTOMER",
                  "is_active": true,
                  "customer_profile": null,
                  "allowed_actions": []
                }
              },
              "error": null,
              "metadata": {
                "correlation_id": "00000000-0000-0000-0000-000000000002"
              }
            }
        """.trimIndent()

        val envelope =
            json.decodeFromString<ApiEnvelope<SessionResponse>>(raw)

        assertTrue(envelope.success)

        val session = requireNotNull(envelope.data)
        assertEquals("access.jwt", session.accessToken)
        assertEquals("refresh.jwt", session.refreshToken)
        assertEquals("Bearer", session.tokenType)
        assertEquals(3600L, session.accessExpiresIn)
        assertEquals("CUSTOMER", session.user.roleCode)
    }

    @Test
    fun validation422_preservesFieldsDetails() = runTest {
        val body = """
            {
              "success": false,
              "data": null,
              "error": {
                "code": "VALIDATION_ERROR",
                "message": "입력값을 확인해 주세요.",
                "details": {
                  "fields": {
                    "username": ["사용할 수 없는 형식입니다."],
                    "password": ["비밀번호 정책을 확인해 주세요."]
                  }
                }
              },
              "metadata": {
                "correlation_id": "00000000-0000-0000-0000-000000000003"
              }
            }
        """.trimIndent()

        val result = safeApiCall<SessionResponse>(json) {
            Response.error(
                422,
                body.toResponseBody("application/json".toMediaType())
            )
        }

        assertTrue(result is ApiResult.Failure)

        val failure = result as ApiResult.Failure
        assertEquals(422, failure.httpStatus)
        assertTrue(failure.details.orEmpty().contains("fields"))
        assertTrue(failure.details.orEmpty().contains("username"))
        assertFalse(failure.retryable)
    }

    @Test
    fun rateLimit429_preservesRetryAfterSecondsAndIsRetryable() = runTest {
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
              },
              "metadata": {
                "correlation_id": "00000000-0000-0000-0000-000000000004"
              }
            }
        """.trimIndent()

        val result = safeApiCall<SessionResponse>(json) {
            Response.error(
                429,
                body.toResponseBody("application/json".toMediaType())
            )
        }

        assertTrue(result is ApiResult.Failure)

        val failure = result as ApiResult.Failure
        assertEquals(429, failure.httpStatus)
        assertTrue(failure.retryable)
        assertTrue(
            failure.details.orEmpty()
                .contains("retry_after_seconds")
        )
        assertTrue(failure.details.orEmpty().contains("60"))
    }
}
