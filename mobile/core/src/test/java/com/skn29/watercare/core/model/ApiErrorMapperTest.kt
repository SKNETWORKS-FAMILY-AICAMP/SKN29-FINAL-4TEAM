package com.skn29.watercare.core.model

import com.skn29.watercare.core.network.ApiErrorMapper
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiErrorMapperTest {
    @Test fun roleAndResourceErrors_areSafeForCustomer() {
        assertTrue(ApiErrorMapper.userMessage(403).contains("역할"))
        assertTrue(ApiErrorMapper.userMessage(404).contains("찾을 수"))
    }

    @Test fun conflictAndServerErrors_haveRecoveryGuidance() {
        assertTrue(ApiErrorMapper.userMessage(409).contains("최신 상태"))
        assertTrue(ApiErrorMapper.userMessage(500).contains("서버"))
    }

    @Test fun validationError_usesSafeMessage() {
        assertTrue(ApiErrorMapper.userMessage(422, "VALIDATION_ERROR").contains("입력값"))
    }

    @Test
    fun clientAndAuthenticationErrors_haveClearMessages() {
        assertTrue(ApiErrorMapper.userMessage(400).contains("요청"))
        assertTrue(ApiErrorMapper.userMessage(401).contains("로그인"))
    }

    @Test
    fun unavailableAndTimeoutErrors_haveRecoveryGuidance() {
        assertTrue(
            ApiErrorMapper.userMessage(
                503,
                "AI-FAILED-01",
            ).contains("다시 시도")
        )
        assertTrue(
            ApiErrorMapper.userMessage(
                504,
                "AI-TIMEOUT-01",
            ).contains("초과")
        )
    }

}
