package com.skn29.watercare.technician

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class TechnicianViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun demoLoginLoadsSyntheticVisitListForTechnician() = runTest(dispatcher) {
        val viewModel = TechnicianViewModel(
            authRepository = FakeAuthRepository(technicianSession()),
            backendStatusRepository = FakeBackendStatusRepository(),
            visitRepository = FakeTechnicianVisitRepository(delayMillis = 0L),
        )

        dispatcher.scheduler.advanceUntilIdle()
        viewModel.demoLogin()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals("TECHNICIAN", viewModel.state.value.user?.roleCode)
        assertEquals(3, viewModel.state.value.visits.size)
        assertFalse(viewModel.state.value.offlinePreview)
        assertNull(viewModel.state.value.error)
    }

    @Test
    fun nonTechnicianLoginIsRejectedWithoutLoadingVisits() = runTest(dispatcher) {
        val viewModel = TechnicianViewModel(
            authRepository = FakeAuthRepository(customerSession()),
            backendStatusRepository = FakeBackendStatusRepository(),
            visitRepository = FakeTechnicianVisitRepository(delayMillis = 0L),
        )

        dispatcher.scheduler.advanceUntilIdle()
        viewModel.demoLogin()
        dispatcher.scheduler.advanceUntilIdle()

        assertNull(viewModel.state.value.user)
        assertTrue(viewModel.state.value.visits.isEmpty())
        assertFalse(viewModel.state.value.loginLoading)
        assertEquals(
            "방문기사 권한이 없는 계정입니다.",
            viewModel.state.value.error,
        )
    }

    @Test
    fun backendFailureCanBeRetriedAfterConnectionRecovers() = runTest(dispatcher) {
        val backendRepository = FakeBackendStatusRepository(available = false)
        val viewModel = TechnicianViewModel(
            authRepository = FakeAuthRepository(technicianSession()),
            backendStatusRepository = backendRepository,
            visitRepository = FakeTechnicianVisitRepository(delayMillis = 0L),
        )

        dispatcher.scheduler.advanceUntilIdle()

        assertFalse(viewModel.state.value.checkingBackend)
        assertEquals(false, viewModel.state.value.backendAvailable)

        backendRepository.available = true
        viewModel.checkBackend()
        dispatcher.scheduler.advanceUntilIdle()

        assertFalse(viewModel.state.value.checkingBackend)
        assertEquals(true, viewModel.state.value.backendAvailable)
    }

    @Test
    fun offlinePreviewIsExplicitAndLoadsFixtureVisits() = runTest(dispatcher) {
        val viewModel = TechnicianViewModel(
            authRepository = FakeAuthRepository(technicianSession()),
            backendStatusRepository = FakeBackendStatusRepository(available = false),
            visitRepository = FakeTechnicianVisitRepository(delayMillis = 0L),
        )

        dispatcher.scheduler.advanceUntilIdle()
        viewModel.startOfflinePreview()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.state.value.offlinePreview)
        assertEquals("합성 기사 001", viewModel.state.value.user?.displayName)
        assertEquals(3, viewModel.state.value.visits.size)
    }

    @Test
    fun openingVisitLoadsPrecheckReport() = runTest(dispatcher) {
        val repository = FakeTechnicianVisitRepository(delayMillis = 0L)
        val firstVisit = (
            repository.getAssignedVisits() as ApiResult.Success
        ).value.first()

        val viewModel = TechnicianViewModel(
            authRepository = FakeAuthRepository(technicianSession()),
            backendStatusRepository = FakeBackendStatusRepository(),
            visitRepository = repository,
        )

        dispatcher.scheduler.advanceUntilIdle()
        viewModel.startOfflinePreview()
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.openVisit(firstVisit.visitId)
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(firstVisit.visitId, viewModel.state.value.selectedVisitId)
        assertNotNull(viewModel.state.value.selectedReport)
        assertEquals(
            firstVisit.visitCode,
            viewModel.state.value.selectedReport?.visitCode,
        )
    }

    @Test
    fun closingVisitClearsSelectedReportState() = runTest(dispatcher) {
        val repository = FakeTechnicianVisitRepository(delayMillis = 0L)
        val firstVisit = (
            repository.getAssignedVisits() as ApiResult.Success
        ).value.first()

        val viewModel = TechnicianViewModel(
            authRepository = FakeAuthRepository(technicianSession()),
            backendStatusRepository = FakeBackendStatusRepository(),
            visitRepository = repository,
        )

        dispatcher.scheduler.advanceUntilIdle()
        viewModel.startOfflinePreview()
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.openVisit(firstVisit.visitId)
        dispatcher.scheduler.advanceUntilIdle()

        assertNotNull(viewModel.state.value.selectedReport)

        viewModel.closeVisit()

        assertNull(viewModel.state.value.selectedVisitId)
        assertNull(viewModel.state.value.selectedReport)
        assertNull(viewModel.state.value.reportError)
        assertFalse(viewModel.state.value.reportLoading)
    }

    private fun technicianSession(): ApiResult<SessionResponse> =
        sessionForRole(
            roleCode = "TECHNICIAN",
            displayName = "합성 기사",
        )

    private fun customerSession(): ApiResult<SessionResponse> =
        sessionForRole(
            roleCode = "CUSTOMER",
            displayName = "합성 고객",
        )

    private fun sessionForRole(
        roleCode: String,
        displayName: String,
    ): ApiResult<SessionResponse> = ApiResult.Success(
        SessionResponse(
            accessToken = "access",
            refreshToken = "refresh",
            tokenType = "Bearer",
            accessExpiresIn = 900L,
            refreshExpiresIn = 3600L,
            user = UserData(
                id = "$roleCode-id",
                displayName = displayName,
                roleCode = roleCode,
                isActive = true,
            ),
        )
    )

    private class FakeAuthRepository(
        private val loginResult: ApiResult<SessionResponse>,
    ) : AuthRepository {
        override fun hasSession(): Boolean = false

        override suspend fun demoLogin(
            code: String,
        ): ApiResult<SessionResponse> = loginResult

        override suspend fun logout(): ApiResult<Unit> = ApiResult.Success(Unit)

        override suspend fun me(): ApiResult<UserData> = when (loginResult) {
            is ApiResult.Success -> ApiResult.Success(loginResult.value.user)
            is ApiResult.Failure -> loginResult
        }
    }

    private class FakeBackendStatusRepository(
        var available: Boolean = true,
    ) : BackendStatusRepository {
        override suspend fun health(): ApiResult<Unit> =
            if (available) {
                ApiResult.Success(Unit)
            } else {
                ApiResult.Failure(
                    code = "NETWORK_ERROR",
                    message = "Backend unavailable",
                    retryable = true,
                )
            }
    }
}
