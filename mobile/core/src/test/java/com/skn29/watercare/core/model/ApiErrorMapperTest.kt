package com.skn29.watercare.core.model

import com.skn29.watercare.core.network.ApiErrorMapper
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiErrorMapperTest {
    @Test
    fun mapsRoleAndOwnershipErrorsSeparately() {
        assertTrue(ApiErrorMapper.userMessage(403).contains("역할"))
        assertTrue(ApiErrorMapper.userMessage(404).contains("찾을 수"))
    }

    @Test
    fun mapsStateConflictAndServerFailureAsSafeMessages() {
        assertTrue(ApiErrorMapper.userMessage(409).contains("최신 상태"))
        assertTrue(ApiErrorMapper.userMessage(500).contains("서버"))
    }

    @Test
    fun mapsBothBadRequestAndUnprocessableEntityAsInputErrors() {
        assertTrue(ApiErrorMapper.userMessage(400).contains("입력"))
        assertTrue(ApiErrorMapper.userMessage(422).contains("입력"))
    }
}
