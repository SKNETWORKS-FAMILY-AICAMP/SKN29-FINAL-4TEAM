package com.skn29.watercare.technician

import com.skn29.watercare.core.model.ApiResult
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TechnicianVisitRepositoryTest {
    private val repository = FakeTechnicianVisitRepository(delayMillis = 0L)

    @Test
    fun assignedVisitsAreSyntheticAndMasked() = runTest {
        val result = repository.getAssignedVisits()

        assertTrue(result is ApiResult.Success)
        val visits = (result as ApiResult.Success).value
        assertEquals(3, visits.size)
        assertTrue(visits.all { it.isSynthetic })
        assertTrue(visits.all { "○" in it.customerMaskedName })
        assertTrue(visits.all { "***" in it.maskedAddress })
    }

    @Test
    fun knownVisitReturnsReadOnlyPrecheckReport() = runTest {
        val visits = (repository.getAssignedVisits() as ApiResult.Success).value
        val result = repository.getPrecheckReport(visits.first().visitId)

        assertTrue(result is ApiResult.Success)
        val report = (result as ApiResult.Success).value
        assertEquals(visits.first().visitCode, report.visitCode)
        assertTrue(report.isSynthetic)
        assertTrue(report.inspectionCandidates.isNotEmpty())
        assertTrue(report.evidence.isNotEmpty())
    }

    @Test
    fun unknownVisitReturnsNotFoundFailure() = runTest {
        val result = repository.getPrecheckReport("missing-visit")

        assertTrue(result is ApiResult.Failure)
        val failure = result as ApiResult.Failure
        assertEquals("VISIT_NOT_FOUND", failure.code)
        assertEquals(404, failure.httpStatus)
    }
}
