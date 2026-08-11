package com.skn29.watercare.customer.feature.customer.home

import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.config.CustomerCareRuntimeConfig
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.SubscriptionDetailDto
import com.skn29.watercare.core.model.SubscriptionListDataDto
import com.skn29.watercare.core.model.SubscriptionProductDto
import com.skn29.watercare.core.model.SubscriptionSummaryDto
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.repository.AuthRepository
import com.skn29.watercare.core.repository.BackendStatusRepository
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.repository.SubscriptionRepository
import com.skn29.watercare.customer.feature.customer.intake.MainDispatcherRule
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CustomerHomeViewModelTest {
    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    @Test
    fun remoteMode_withoutDemoUuid_loadsActualSubscriptionAndEnablesIntake() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeSubscriptionRepository(
                items = listOf(summary("sub-1")),
            )
            val viewModel = createViewModel(
                config = CustomerCareRuntimeConfig.from("REMOTE", ""),
                offlinePreview = false,
                subscriptionRepository = repository,
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals(CustomerCareMode.REMOTE, state.customerCareMode)
            assertEquals("sub-1", state.home?.subscriptionId)
            assertEquals("sub-1", state.selectedSubscriptionId)
            assertEquals(1, state.subscriptions.size)
            assertTrue(state.intakeAvailable)
            assertNull(state.intakeUnavailableReason)
            assertTrue(state.dataSourceLabel.contains("구독 목록·상세·문의 실제 API"))
            assertEquals(1, repository.listCalls)
            assertEquals(listOf("sub-1"), repository.detailCalls)
        }

    @Test
    fun remoteMode_selectsAnotherActualSubscriptionByPublicId() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeSubscriptionRepository(
                items = listOf(
                    summary("sub-1"),
                    summary("sub-2"),
                ),
            )
            val viewModel = createViewModel(
                config = CustomerCareRuntimeConfig.from("REMOTE", ""),
                offlinePreview = false,
                subscriptionRepository = repository,
            )

            advanceUntilIdle()
            viewModel.selectSubscription("sub-2")
            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals("sub-2", state.selectedSubscriptionId)
            assertEquals("sub-2", state.home?.subscriptionId)
            assertTrue(state.intakeAvailable)
            assertEquals(listOf("sub-1", "sub-2"), repository.detailCalls)
        }

    @Test
    fun remoteMode_emptySubscriptionList_blocksIntakeWithoutFakeFallback() =
        runTest(mainDispatcherRule.dispatcher) {
            val viewModel = createViewModel(
                config = CustomerCareRuntimeConfig.from("REMOTE", ""),
                offlinePreview = false,
                subscriptionRepository = FakeSubscriptionRepository(items = emptyList()),
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertNull(state.home)
            assertTrue(state.subscriptions.isEmpty())
            assertFalse(state.intakeAvailable)
            assertEquals("SUBSCRIPTION_EMPTY", state.errorCode)
            assertTrue(state.intakeUnavailableReason.orEmpty().contains("구독이 없습니다"))
        }

    @Test
    fun inactiveSubscription_isVisibleButCannotStartInquiry() =
        runTest(mainDispatcherRule.dispatcher) {
            val viewModel = createViewModel(
                config = CustomerCareRuntimeConfig.from("REMOTE", ""),
                offlinePreview = false,
                subscriptionRepository = FakeSubscriptionRepository(
                    items = listOf(summary("sub-ended", status = "ENDED")),
                ),
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals("sub-ended", state.home?.subscriptionId)
            assertFalse(state.intakeAvailable)
            assertTrue(state.intakeUnavailableReason.orEmpty().contains("활성 구독"))
        }

    @Test
    fun unsupportedModel_isVisibleButCannotStartInquiry() =
        runTest(mainDispatcherRule.dispatcher) {
            val viewModel = createViewModel(
                config = CustomerCareRuntimeConfig.from("REMOTE", ""),
                offlinePreview = false,
                subscriptionRepository = FakeSubscriptionRepository(
                    items = listOf(
                        summary("sub-other", modelCode = "OTHER-MODEL")
                    ),
                ),
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertFalse(state.intakeAvailable)
            assertTrue(state.intakeUnavailableReason.orEmpty().contains(P0_SUPPORTED_MODEL_CODE))
        }

    @Test
    fun subscriptionList401_isExposedAndDoesNotFallBackToFixture() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeSubscriptionRepository(
                listFailure = ApiResult.Failure(
                    code = "AUTHENTICATION_REQUIRED",
                    message = "로그인이 만료되었습니다.",
                    httpStatus = 401,
                ),
            )
            val viewModel = createViewModel(
                config = CustomerCareRuntimeConfig.from("REMOTE", ""),
                offlinePreview = false,
                subscriptionRepository = repository,
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertNull(state.home)
            assertEquals(401, state.errorHttpStatus)
            assertEquals("AUTHENTICATION_REQUIRED", state.errorCode)
            assertFalse(state.intakeAvailable)
        }

    @Test
    fun subscriptionDetail404_keepsListButBlocksIntake() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeSubscriptionRepository(
                items = listOf(summary("sub-404")),
                detailFailureById = mapOf(
                    "sub-404" to ApiResult.Failure(
                        code = "NOT_FOUND",
                        message = "구독을 찾을 수 없습니다.",
                        httpStatus = 404,
                    )
                ),
            )
            val viewModel = createViewModel(
                config = CustomerCareRuntimeConfig.from("REMOTE", ""),
                offlinePreview = false,
                subscriptionRepository = repository,
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals(1, state.subscriptions.size)
            assertEquals(404, state.errorHttpStatus)
            assertFalse(state.intakeAvailable)
        }

    @Test
    fun networkFailure_isVisibleAndDoesNotUseFakeHome() =
        runTest(mainDispatcherRule.dispatcher) {
            val repository = FakeSubscriptionRepository(
                listFailure = ApiResult.Failure(
                    code = "NETWORK_ERROR",
                    message = "네트워크 연결을 확인해 주세요.",
                    retryable = true,
                ),
            )
            val viewModel = createViewModel(
                config = CustomerCareRuntimeConfig.from("REMOTE", ""),
                offlinePreview = false,
                subscriptionRepository = repository,
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertNull(state.home)
            assertEquals("NETWORK_ERROR", state.errorCode)
            assertFalse(state.intakeAvailable)
        }

    @Test
    fun fakeMode_offlinePreview_keepsSyntheticIntakeAvailable() =
        runTest(mainDispatcherRule.dispatcher) {
            val config = CustomerCareRuntimeConfig.from("FAKE", "")
            val viewModel = createViewModel(
                config = config,
                offlinePreview = true,
                subscriptionRepository = null,
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertEquals(CustomerCareMode.FAKE, state.customerCareMode)
            assertTrue(state.intakeAvailable)
            assertFalse(state.backendAvailable ?: true)
            assertTrue(state.dataSourceLabel.contains("Demo Mock"))
        }

    @Test
    fun remoteMode_offlinePreview_blocksAccidentalNetworkWrite() =
        runTest(mainDispatcherRule.dispatcher) {
            val config = CustomerCareRuntimeConfig.from("REMOTE", "")
            val viewModel = createViewModel(
                config = config,
                offlinePreview = true,
                subscriptionRepository = null,
            )

            advanceUntilIdle()

            val state = viewModel.state.value
            assertFalse(state.intakeAvailable)
            assertTrue(state.intakeUnavailableReason.orEmpty().contains("FAKE"))
            assertTrue(state.dataSourceLabel.contains("문의 전송 차단"))
        }

    private fun createViewModel(
        config: CustomerCareRuntimeConfig,
        offlinePreview: Boolean,
        subscriptionRepository: SubscriptionRepository?,
    ) = CustomerHomeViewModel(
        authRepository = SuccessAuthRepository,
        careRepository = FakeCustomerCareRepository(config.fixtureSubscriptionId),
        subscriptionRepository = subscriptionRepository,
        backendStatusRepository = SuccessBackendStatusRepository,
        runtimeConfig = config,
        offlinePreview = offlinePreview,
    )

    private fun summary(
        id: String,
        status: String = "ACTIVE",
        modelCode: String = P0_SUPPORTED_MODEL_CODE,
    ) = SubscriptionSummaryDto(
        subscriptionId = id,
        statusCode = status,
        managementTypeCode = "VISIT_CARE",
        startedOn = "2026-07-01",
        lastCareOn = null,
        nextCareOn = "2026-09-03",
        product = SubscriptionProductDto(
            productModelId = "model-$id",
            modelCode = modelCode,
            modelName = "WPU-JAC104D",
            generationCode = "D",
            manufacturer = "SK magic",
        ),
    )

    private class FakeSubscriptionRepository(
        private val items: List<SubscriptionSummaryDto> = emptyList(),
        private val listFailure: ApiResult.Failure? = null,
        private val detailFailureById: Map<String, ApiResult.Failure> = emptyMap(),
    ) : SubscriptionRepository {
        var listCalls = 0
            private set
        val detailCalls = mutableListOf<String>()

        override suspend fun list(
            page: Int,
            size: Int,
        ): ApiResult<SubscriptionListDataDto> {
            listCalls += 1
            return listFailure ?: ApiResult.Success(
                SubscriptionListDataDto(
                    items = items,
                    page = page,
                    size = size,
                    total = items.size,
                )
            )
        }

        override suspend fun detail(
            subscriptionId: String,
        ): ApiResult<SubscriptionDetailDto> {
            detailCalls += subscriptionId
            detailFailureById[subscriptionId]?.let { return it }
            val item = items.first { it.subscriptionId == subscriptionId }
            return ApiResult.Success(
                SubscriptionDetailDto(
                    subscriptionId = item.subscriptionId,
                    statusCode = item.statusCode,
                    managementTypeCode = item.managementTypeCode,
                    startedOn = item.startedOn,
                    lastCareOn = item.lastCareOn,
                    nextCareOn = item.nextCareOn,
                    endedOn = null,
                    product = item.product,
                )
            )
        }
    }

    private object SuccessBackendStatusRepository : BackendStatusRepository {
        override suspend fun health(): ApiResult<Unit> = ApiResult.Success(Unit)
    }

    private object SuccessAuthRepository : AuthRepository {
        override fun hasSession(): Boolean = true

        override suspend fun demoLogin(code: String): ApiResult<SessionResponse> =
            error("이 테스트에서는 사용하지 않습니다.")

        override suspend fun logout(): ApiResult<Unit> = ApiResult.Success(Unit)

        override suspend fun me(): ApiResult<UserData> = ApiResult.Success(
            UserData(
                id = "user-id",
                displayName = "합성 고객",
                roleCode = "CUSTOMER",
                isActive = true,
            )
        )
    }
}
