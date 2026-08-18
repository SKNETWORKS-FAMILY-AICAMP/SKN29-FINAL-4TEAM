package com.skn29.watercare.customer.feature.customer.care

import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CareHistoryCreateRequestDto
import com.skn29.watercare.core.model.CareHistoryItemDto
import com.skn29.watercare.core.model.CareHistoryListDataDto
import com.skn29.watercare.core.model.CareHistoryMutationResultDto
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.SubscriptionDetailDto
import com.skn29.watercare.core.model.SubscriptionListDataDto
import com.skn29.watercare.core.model.SubscriptionProductDto
import com.skn29.watercare.core.model.SubscriptionSummaryDto
import com.skn29.watercare.core.repository.CareHistoryRepository
import com.skn29.watercare.core.repository.SubscriptionRepository
import com.skn29.watercare.customer.feature.customer.intake.MainDispatcherRule
import java.time.LocalDate
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CareHistoryViewModelTest {
    @get:Rule
    val mainDispatcherRule =
        MainDispatcherRule()

    private val today =
        LocalDate.parse("2026-08-18")

    @Test
    fun load_keepsOnlyOwnActiveSupportedSubscriptionInput() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val subscriptions =
                FakeSubscriptionRepository(
                    listOf(
                        subscription(
                            id = "active-supported",
                        ),
                        subscription(
                            id = "inactive-supported",
                            status = "ENDED",
                        ),
                        subscription(
                            id = "active-unsupported",
                            modelCode =
                                "UNSUPPORTED",
                        ),
                    )
                )
            val care =
                RecordingCareRepository()

            val viewModel =
                newViewModel(
                    subscriptions,
                    care,
                )

            advanceUntilIdle()

            assertEquals(
                listOf("active-supported"),
                viewModel.state.value
                    .subscriptions
                    .map {
                        it.subscriptionId
                    },
            )
            assertEquals(
                "active-supported",
                viewModel.state.value
                    .selectedSubscriptionId,
            )
            assertEquals(
                listOf("active-supported"),
                care.listSubscriptionIds,
            )
        }

    @Test
    fun rapidDoubleCreate_callsRepositoryOnce() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val care =
                RecordingCareRepository(
                    createResult =
                        ApiResult.Success(
                            mutation(
                                replay = false
                            )
                        )
                )
            val viewModel =
                newViewModel(
                    FakeSubscriptionRepository(
                        listOf(
                            subscription()
                        )
                    ),
                    care,
                )
            advanceUntilIdle()

            viewModel.updatePerformedOn(
                today.toString()
            )
            viewModel.createCareRecord()
            viewModel.createCareRecord()

            assertTrue(
                viewModel.state.value
                    .isCreating
            )

            advanceUntilIdle()

            assertEquals(1, care.createCalls)
        }

    @Test
    fun replaySuccess_isShownAsSafeReplay() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val care =
                RecordingCareRepository(
                    createResult =
                        ApiResult.Success(
                            mutation(
                                replay = true
                            )
                        )
                )
            val viewModel =
                newViewModel(
                    FakeSubscriptionRepository(
                        listOf(
                            subscription()
                        )
                    ),
                    care,
                )
            advanceUntilIdle()

            viewModel.createCareRecord()
            advanceUntilIdle()

            assertTrue(
                viewModel.state.value
                    .notice
                    .orEmpty()
                    .contains("동일 요청")
            )
        }

    @Test
    fun conflict409_mapsToConflictWithoutRawBackendMessage() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val care =
                RecordingCareRepository(
                    createResult =
                        ApiResult.Failure(
                            code =
                                "DUPLICATE-EVENT-01",
                            message =
                                "raw backend conflict",
                            httpStatus = 409,
                        )
                )
            val viewModel =
                newViewModel(
                    FakeSubscriptionRepository(
                        listOf(
                            subscription()
                        )
                    ),
                    care,
                )
            advanceUntilIdle()

            viewModel.createCareRecord()
            advanceUntilIdle()

            val state =
                viewModel.state.value
            assertEquals(
                CareHistoryErrorKind.CONFLICT,
                state.errorKind,
            )
            assertFalse(
                state.errorMessage
                    .orEmpty()
                    .contains(
                        "raw backend conflict"
                    )
            )
        }

    @Test
    fun masked404_doesNotExposeOwnerOrObjectDetail() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val care =
                RecordingCareRepository(
                    createResult =
                        ApiResult.Failure(
                            code = "NOT_FOUND",
                            message =
                                "OTHER_USER_SUBSCRIPTION",
                            httpStatus = 404,
                        )
                )
            val viewModel =
                newViewModel(
                    FakeSubscriptionRepository(
                        listOf(
                            subscription()
                        )
                    ),
                    care,
                )
            advanceUntilIdle()

            viewModel.createCareRecord()
            advanceUntilIdle()

            val state =
                viewModel.state.value
            assertEquals(
                CareHistoryErrorKind.NOT_FOUND,
                state.errorKind,
            )
            assertEquals(
                "케어 이력을 확인할 수 없어요.",
                state.errorMessage,
            )
            assertFalse(
                state.errorMessage
                    .orEmpty()
                    .contains(
                        "OTHER_USER"
                    )
            )
        }

    @Test
    fun validation422_mapsToValidationBoundary() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val care =
                RecordingCareRepository(
                    createResult =
                        ApiResult.Failure(
                            code =
                                "VALIDATION_ERROR",
                            message =
                                "server detail",
                            httpStatus = 422,
                        )
                )
            val viewModel =
                newViewModel(
                    FakeSubscriptionRepository(
                        listOf(
                            subscription()
                        )
                    ),
                    care,
                )
            advanceUntilIdle()

            viewModel.createCareRecord()
            advanceUntilIdle()

            assertEquals(
                CareHistoryErrorKind.VALIDATION,
                viewModel.state.value
                    .errorKind,
            )
        }

    @Test
    fun futureDate_isRejectedBeforeRepositoryCall() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val care =
                RecordingCareRepository()
            val viewModel =
                newViewModel(
                    FakeSubscriptionRepository(
                        listOf(
                            subscription()
                        )
                    ),
                    care,
                )
            advanceUntilIdle()

            viewModel.updatePerformedOn(
                "2026-08-19"
            )
            viewModel.createCareRecord()
            advanceUntilIdle()

            assertEquals(0, care.createCalls)
            assertEquals(
                CareHistoryErrorKind.VALIDATION,
                viewModel.state.value
                    .errorKind,
            )
        }

    @Test
    fun dateBeforeSubscriptionStart_isRejectedBeforeRepositoryCall() =
        runTest(
            mainDispatcherRule.dispatcher
        ) {
            val care =
                RecordingCareRepository()
            val viewModel =
                newViewModel(
                    FakeSubscriptionRepository(
                        listOf(
                            subscription(
                                startedOn =
                                    "2026-08-10"
                            )
                        )
                    ),
                    care,
                )
            advanceUntilIdle()

            viewModel.updatePerformedOn(
                "2026-08-09"
            )
            viewModel.createCareRecord()
            advanceUntilIdle()

            assertEquals(0, care.createCalls)
            assertEquals(
                CareHistoryErrorKind.VALIDATION,
                viewModel.state.value
                    .errorKind,
            )
        }

    private fun newViewModel(
        subscriptions:
            SubscriptionRepository,
        care:
            CareHistoryRepository,
    ) = CareHistoryViewModel(
        subscriptionRepository =
            subscriptions,
        careHistoryRepository = care,
        todayProvider = { today },
    )

    private fun subscription(
        id: String = "subscription",
        status: String = "ACTIVE",
        modelCode: String =
            P0_SUPPORTED_MODEL_CODE,
        startedOn: String =
            "2026-01-01",
    ) = SubscriptionSummaryDto(
        subscriptionId = id,
        statusCode = status,
        managementTypeCode =
            "SELF_MANAGED",
        startedOn = startedOn,
        lastCareOn = null,
        nextCareOn = null,
        product =
            SubscriptionProductDto(
                productModelId =
                    "product-$id",
                modelCode = modelCode,
                modelName = "테스트 정수기",
                generationCode = null,
                manufacturer = "SK매직",
            ),
    )

    private fun mutation(
        replay: Boolean,
    ) = CareHistoryMutationResultDto(
        careRecordId = "care-record",
        subscriptionId = "subscription",
        careTypeCode =
            "FILTER_REPLACEMENT",
        statusCode = "COMPLETED",
        performedOn = today.toString(),
        resultCode = "FILTER_REPLACED",
        sourceCode = "CUSTOMER",
        idempotentReplay = replay,
    )

    private class FakeSubscriptionRepository(
        private val items:
            List<SubscriptionSummaryDto>,
    ) : SubscriptionRepository {
        override suspend fun list(
            page: Int,
            size: Int,
        ): ApiResult<SubscriptionListDataDto> =
            ApiResult.Success(
                SubscriptionListDataDto(
                    items = items,
                    page = page,
                    size = size,
                    total = items.size,
                )
            )

        override suspend fun detail(
            subscriptionId: String,
        ): ApiResult<SubscriptionDetailDto> =
            error("unused")
    }

    private class RecordingCareRepository(
        private val createResult:
            ApiResult<CareHistoryMutationResultDto> =
            ApiResult.Failure(
                code = "NETWORK_ERROR",
                message = "network",
                retryable = true,
            ),
    ) : CareHistoryRepository {
        var createCalls = 0
        val listSubscriptionIds =
            mutableListOf<String>()

        override suspend fun list(
            subscriptionId: String,
            page: Int,
            size: Int,
        ): ApiResult<CareHistoryListDataDto> {
            listSubscriptionIds +=
                subscriptionId
            return ApiResult.Success(
                CareHistoryListDataDto(
                    items = emptyList(),
                    page = page,
                    size = size,
                    total = 0,
                )
            )
        }

        override suspend fun detail(
            subscriptionId: String,
            careRecordId: String,
        ): ApiResult<CareHistoryItemDto> =
            error("unused")

        override suspend fun create(
            subscriptionId: String,
            request:
                CareHistoryCreateRequestDto,
            idempotencyKeyOverride:
                String?,
        ): ApiResult<CareHistoryMutationResultDto> {
            createCalls += 1
            return createResult
        }
    }
}