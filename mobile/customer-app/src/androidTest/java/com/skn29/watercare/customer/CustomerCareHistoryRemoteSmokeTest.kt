package com.skn29.watercare.customer

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CareHistoryCreateRequestDto
import com.skn29.watercare.core.model.CareHistoryItemDto
import com.skn29.watercare.core.model.CareHistoryListDataDto
import com.skn29.watercare.core.model.CareHistoryMutationResultDto
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.SubscriptionListDataDto
import java.time.LocalDate
import java.time.ZoneId
import java.util.UUID
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CustomerCareHistoryRemoteSmokeTest {
    @Test
    fun ownerActiveSupported_listDetailCreateAndBoundaries_realBackend() =
        runBlocking<Unit> {
            val args =
                InstrumentationRegistry
                    .getArguments()
            assumeTrue(
                args.getString(
                    "runRemoteCareSmoke"
                ) == "true"
            )

            val context =
                InstrumentationRegistry
                    .getInstrumentation()
                    .targetContext
            WaterCareCore.initialize(
                context = context,
                baseUrl =
                    BuildConfig
                        .BACKEND_BASE_URL,
                debug = true,
                customerCareMode =
                    "REMOTE",
                demoSubscriptionId = "",
            )

            val login =
                WaterCareCore
                    .authRepository
                    .demoLogin(
                        BuildConfig
                            .E2E_CUSTOMER_CODE
                    )
            assertTrue(
                login is
                    ApiResult.Success<*>
            )
            val session =
                (
                    login as
                        ApiResult.Success<
                            SessionResponse
                        >
                    ).value
            assertEquals(
                "CUSTOMER",
                session.user.roleCode,
            )

            val subscriptions =
                WaterCareCore
                    .subscriptionRepository
                    .list(
                        page = 1,
                        size = 100,
                    )
            assertTrue(
                subscriptions is
                    ApiResult.Success<*>
            )
            val subscriptionData =
                (
                    subscriptions as
                        ApiResult.Success<
                            SubscriptionListDataDto
                        >
                    ).value

            val target =
                subscriptionData.items
                    .firstOrNull {
                        it.statusCode ==
                            "ACTIVE" &&
                            it.product.modelCode ==
                            P0_SUPPORTED_MODEL_CODE
                    }
            assumeTrue(target != null)
            val subscription =
                requireNotNull(target)

            val beforeList =
                WaterCareCore
                    .careHistoryRepository
                    .list(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        page = 1,
                        size = 100,
                    )
            assertTrue(
                beforeList is
                    ApiResult.Success<*>
            )
            val beforeData =
                (
                    beforeList as
                        ApiResult.Success<
                            CareHistoryListDataDto
                        >
                    ).value
            assertTrue(
                beforeData.items.all {
                    it.statusCode ==
                        "COMPLETED"
                }
            )

            val today =
                LocalDate.now(
                    ZoneId.of(
                        "Asia/Seoul"
                    )
                ).toString()
            val key =
                UUID.randomUUID()
                    .toString()
            val request =
                CareHistoryCreateRequestDto(
                    careTypeCode =
                        "CLEANING",
                    performedOn = today,
                )

            val created =
                WaterCareCore
                    .careHistoryRepository
                    .create(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        request = request,
                        idempotencyKeyOverride =
                            key,
                    )
            assertTrue(
                created is
                    ApiResult.Success<*>
            )
            val createdData =
                (
                    created as
                        ApiResult.Success<
                            CareHistoryMutationResultDto
                        >
                    ).value
            assertFalse(
                createdData.idempotentReplay
            )
            assertEquals(
                "COMPLETED",
                createdData.statusCode,
            )
            assertEquals(
                "CLEANING",
                createdData.careTypeCode,
            )
            assertEquals(
                "CUSTOMER",
                createdData.sourceCode,
            )
            assertEquals(
                "NORMAL",
                createdData.resultCode,
            )

            val replay =
                WaterCareCore
                    .careHistoryRepository
                    .create(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        request = request,
                        idempotencyKeyOverride =
                            key,
                    )
            assertTrue(
                replay is
                    ApiResult.Success<*>
            )
            val replayData =
                (
                    replay as
                        ApiResult.Success<
                            CareHistoryMutationResultDto
                        >
                    ).value
            assertTrue(
                replayData.idempotentReplay
            )
            assertEquals(
                createdData.careRecordId,
                replayData.careRecordId,
            )

            val conflict =
                WaterCareCore
                    .careHistoryRepository
                    .create(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        request =
                            CareHistoryCreateRequestDto(
                                careTypeCode =
                                    "FILTER_REPLACEMENT",
                                performedOn =
                                    today,
                            ),
                        idempotencyKeyOverride =
                            key,
                    )
            assertTrue(
                conflict is
                    ApiResult.Failure
            )
            assertEquals(
                409,
                (
                    conflict as
                        ApiResult.Failure
                    ).httpStatus,
            )

            val detail =
                WaterCareCore
                    .careHistoryRepository
                    .detail(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        careRecordId =
                            createdData
                                .careRecordId,
                    )
            assertTrue(
                detail is
                    ApiResult.Success<*>
            )
            val detailData =
                (
                    detail as
                        ApiResult.Success<
                            CareHistoryItemDto
                        >
                    ).value
            assertEquals(
                createdData.careRecordId,
                detailData.careRecordId,
            )
            assertEquals(
                "COMPLETED",
                detailData.statusCode,
            )

            val afterList =
                WaterCareCore
                    .careHistoryRepository
                    .list(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        page = 1,
                        size = 100,
                    )
            assertTrue(
                afterList is
                    ApiResult.Success<*>
            )
            val afterData =
                (
                    afterList as
                        ApiResult.Success<
                            CareHistoryListDataDto
                        >
                    ).value
            assertTrue(
                afterData.items.any {
                    it.careRecordId ==
                        createdData
                            .careRecordId
                }
            )

            val masked404 =
                WaterCareCore
                    .careHistoryRepository
                    .list(
                        subscriptionId =
                            UUID.randomUUID()
                                .toString(),
                    )
            assertTrue(
                masked404 is
                    ApiResult.Failure
            )
            assertEquals(
                404,
                (
                    masked404 as
                        ApiResult.Failure
                    ).httpStatus,
            )

            val unsupportedType =
                WaterCareCore
                    .careHistoryRepository
                    .create(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        request =
                            CareHistoryCreateRequestDto(
                                careTypeCode =
                                    "OTHER",
                                performedOn =
                                    today,
                            ),
                        idempotencyKeyOverride =
                            UUID.randomUUID()
                                .toString(),
                    )
            assertTrue(
                unsupportedType is
                    ApiResult.Failure
            )
            assertEquals(
                422,
                (
                    unsupportedType as
                        ApiResult.Failure
                    ).httpStatus,
            )

            val futureDate =
                WaterCareCore
                    .careHistoryRepository
                    .create(
                        subscriptionId =
                            subscription
                                .subscriptionId,
                        request =
                            CareHistoryCreateRequestDto(
                                careTypeCode =
                                    "CLEANING",
                                performedOn =
                                    LocalDate.parse(
                                        today
                                    )
                                        .plusDays(1)
                                        .toString(),
                            ),
                        idempotencyKeyOverride =
                            UUID.randomUUID()
                                .toString(),
                    )
            assertTrue(
                futureDate is
                    ApiResult.Failure
            )
            assertEquals(
                422,
                (
                    futureDate as
                        ApiResult.Failure
                    ).httpStatus,
            )

            Log.i(
                "CustomerCareHistorySmoke",
                "subscription_id=${subscription.subscriptionId} " +
                    "care_record_id=${createdData.careRecordId} " +
                    "list_before=${beforeData.total} " +
                    "list_after=${afterData.total} " +
                    "replay=${replayData.idempotentReplay} " +
                    "conflict=409 masked=404 validation=422"
            )
        }
}