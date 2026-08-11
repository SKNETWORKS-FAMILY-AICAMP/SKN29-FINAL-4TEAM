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
    fun storedTechnicianSession_restoresAuthButDoesNotLeakFixtureIntoRemoteMode() =
        runTest(dispatcher) {
            val authRepository = FakeAuthRepository(
                loginResult = technicianSession(),
                storedSession = true,
                meResult = technicianUserResult(),
            )
            val viewModel = createViewModel(authRepository)

            dispatcher.scheduler.advanceUntilIdle()

            assertEquals("TECHNICIAN", viewModel.state.value.user?.roleCode)
            assertTrue(viewModel.state.value.visits.isEmpty())
            assertTrue(viewModel.state.value.visitRuntimeBlocked)
            assertTrue(viewModel.state.value.error.orEmpty().contains("방문"))
            assertFalse(viewModel.state.value.offlinePreview)
        }

    @Test
    fun demoLogin_usesActualAuthAndKeepsVisitRuntimeBlocked() =
        runTest(dispatcher) {
            val authRepository = FakeAuthRepository(technicianSession())
            val viewModel = createViewModel(authRepository)

            dispatcher.scheduler.advanceUntilIdle()
            viewModel.demoLogin()
            dispatcher.scheduler.advanceUntilIdle()

            assertEquals("TECHNICIAN", viewModel.state.value.user?.roleCode)
            assertTrue(viewModel.state.value.visits.isEmpty())
            assertTrue(viewModel.state.value.visitRuntimeBlocked)
            assertFalse(viewModel.state.value.offlinePreview)
            assertEquals(1, authRepository.demoLoginCalls)
        }

    @Test
    fun offlinePreview_isExplicitAndLoadsOnlySyntheticVisits() =
        runTest(dispatcher) {
            val viewModel = createViewModel(
                FakeAuthRepository(technicianSession()),
                backendAvailable = false,
            )

            dispatcher.scheduler.advanceUntilIdle()
            viewModel.startOfflinePreview()
            dispatcher.scheduler.advanceUntilIdle()

            assertTrue(viewModel.state.value.offlinePreview)
            assertFalse(viewModel.state.value.visitRuntimeBlocked)
            assertEquals("합성 기사 001", viewModel.state.value.user?.displayName)
            assertEquals(3, viewModel.state.value.visits.size)
            assertNull(viewModel.state.value.error)
        }

    @Test
    fun storedCustomerSession_isRejectedAndCleared() = runTest(dispatcher) {
        val authRepository = FakeAuthRepository(
            loginResult = customerSession(),
            storedSession = true,
            meResult = customerUserResult(),
        )
        val viewModel = createViewModel(authRepository)

        dispatcher.scheduler.advanceUntilIdle()

        assertNull(viewModel.state.value.user)
        assertTrue(viewModel.state.value.visits.isEmpty())
        assertEquals(1, authRepository.logoutCalls)
        assertEquals(
            "저장된 계정에 방문기사 권한이 없습니다. 다시 로그인해 주세요.",
            viewModel.state.value.error,
        )
    }

    @Test
    fun expiredStoredSession_isCleared() = runTest(dispatcher) {
        val authRepository = FakeAuthRepository(
            loginResult = technicianSession(),
            storedSession = true,
            meResult = ApiResult.Failure(
                code = "AUTHENTICATION_REQUIRED",
                message = "인증이 필요합니다.",
                httpStatus = 401,
            ),
        )
        val viewModel = createViewModel(authRepository)

        dispatcher.scheduler.advanceUntilIdle()

        assertNull(viewModel.state.value.user)
        assertEquals(1, authRepository.logoutCalls)
        assertEquals(
            "로그인 세션이 만료되었습니다. 다시 로그인해 주세요.",
            viewModel.state.value.error,
        )
    }

    @Test
    fun backendReconnect_restoresSessionButVisitStillFailsClosed() =
        runTest(dispatcher) {
            val authRepository = FakeAuthRepository(
                loginResult = technicianSession(),
                storedSession = true,
                meResult = technicianUserResult(),
            )
            val backendRepository = FakeBackendStatusRepository(available = false)
            val viewModel = createViewModel(
                authRepository = authRepository,
                backendRepository = backendRepository,
            )

            dispatcher.scheduler.advanceUntilIdle()
            assertNull(viewModel.state.value.user)

            backendRepository.available = true
            viewModel.checkBackend()
            dispatcher.scheduler.advanceUntilIdle()

            assertEquals("TECHNICIAN", viewModel.state.value.user?.roleCode)
            assertTrue(viewModel.state.value.visits.isEmpty())
            assertTrue(viewModel.state.value.visitRuntimeBlocked)
        }

    @Test
    fun openingVisit_inOfflinePreviewLoadsFixturePrecheckReport() =
        runTest(dispatcher) {
            val fixture = FakeTechnicianVisitRepository(delayMillis = 0L)
            val firstVisit = (
                fixture.getAssignedVisits() as ApiResult.Success
            ).value.first()
            val viewModel = createViewModel(
                authRepository = FakeAuthRepository(technicianSession()),
                fixtureRepository = fixture,
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
    fun closingVisit_clearsSelectedReportState() = runTest(dispatcher) {
        val fixture = FakeTechnicianVisitRepository(delayMillis = 0L)
        val firstVisit = (
            fixture.getAssignedVisits() as ApiResult.Success
        ).value.first()
        val viewModel = createViewModel(
            authRepository = FakeAuthRepository(technicianSession()),
            fixtureRepository = fixture,
        )

        dispatcher.scheduler.advanceUntilIdle()
        viewModel.startOfflinePreview()
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.openVisit(firstVisit.visitId)
        dispatcher.scheduler.advanceUntilIdle()

        viewModel.closeVisit()

        assertNull(viewModel.state.value.selectedVisitId)
        assertNull(viewModel.state.value.selectedReport)
        assertNull(viewModel.state.value.reportError)
        assertFalse(viewModel.state.value.reportLoading)
    }

    private fun createViewModel(
        authRepository: AuthRepository,
        backendAvailable: Boolean = true,
        backendRepository: FakeBackendStatusRepository =
            FakeBackendStatusRepository(backendAvailable),
        fixtureRepository: TechnicianVisitRepository =
            FakeTechnicianVisitRepository(delayMillis = 0L),
    ) = TechnicianViewModel(
        authRepository = authRepository,
        backendStatusRepository = backendRepository,
        remoteVisitRepository = BlockedTechnicianVisitRepository(),
        fixtureVisitRepository = fixtureRepository,
    )

    private fun technicianSession(): ApiResult<SessionResponse> =
        sessionForRole("TECHNICIAN", "합성 기사")

    private fun customerSession(): ApiResult<SessionResponse> =
        sessionForRole("CUSTOMER", "합성 고객")

    private fun technicianUserResult(): ApiResult<UserData> =
        ApiResult.Success(userForRole("TECHNICIAN", "합성 기사"))

    private fun customerUserResult(): ApiResult<UserData> =
        ApiResult.Success(userForRole("CUSTOMER", "합성 고객"))

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
            user = userForRole(roleCode, displayName),
        )
    )

    private fun userForRole(
        roleCode: String,
        displayName: String,
    ) = UserData(
        id = "$roleCode-id",
        displayName = displayName,
        roleCode = roleCode,
        isActive = true,
    )

    private class FakeAuthRepository(
        private val loginResult: ApiResult<SessionResponse>,
        private var storedSession: Boolean = false,
        private val meResult: ApiResult<UserData> = when (loginResult) {
            is ApiResult.Success -> ApiResult.Success(loginResult.value.user)
            is ApiResult.Failure -> loginResult
        },
    ) : AuthRepository {
        var meCalls: Int = 0
            private set
        var demoLoginCalls: Int = 0
            private set
        var logoutCalls: Int = 0
            private set

        override fun hasSession(): Boolean = storedSession

        override suspend fun demoLogin(
            code: String,
        ): ApiResult<SessionResponse> {
            demoLoginCalls += 1
            if (loginResult is ApiResult.Success) storedSession = true
            return loginResult
        }

        override suspend fun logout(): ApiResult<Unit> {
            logoutCalls += 1
            storedSession = false
            return ApiResult.Success(Unit)
        }

        override suspend fun me(): ApiResult<UserData> {
            meCalls += 1
            return meResult
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
