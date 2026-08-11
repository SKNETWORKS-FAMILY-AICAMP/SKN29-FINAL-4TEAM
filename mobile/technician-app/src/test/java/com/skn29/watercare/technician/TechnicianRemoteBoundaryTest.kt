package com.skn29.watercare.technician

import com.skn29.watercare.core.model.ApiResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TechnicianRemoteBoundaryTest {
    @Test
    fun remoteRepository_failsClosedWhenVisitRuntimeIsNotRouted() = runBlocking {
        val repository = BlockedTechnicianVisitRepository()

        val list = repository.getAssignedVisits()
        val detail = repository.getPrecheckReport("visit-id")

        assertTrue(list is ApiResult.Failure)
        assertTrue(detail is ApiResult.Failure)
        assertEquals(
            VISIT_RUNTIME_UNAVAILABLE_CODE,
            (list as ApiResult.Failure).code,
        )
        assertEquals(
            VISIT_RUNTIME_UNAVAILABLE_CODE,
            (detail as ApiResult.Failure).code,
        )
    }
}
