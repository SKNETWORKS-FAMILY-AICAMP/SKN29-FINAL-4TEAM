package com.skn29.watercare.customer

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.model.CancelInquiryRequest
import com.skn29.watercare.core.model.AuthTokens
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.DemoLoginRequest
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.SubmitSymptomRequest
import com.skn29.watercare.core.network.NetworkFactory
import java.util.UUID
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CustomerFollowUpCancelRemoteSmokeTest {
    @Test
    fun createQuestionnaireCancelAndVerifyCancelled() =
        runBlocking {
            val args =
                InstrumentationRegistry
                    .getArguments()

            assumeTrue(
                args.getString(
                    "runRemoteCancelSmoke"
                ) == "true"
            )

            val context =
                InstrumentationRegistry
                    .getInstrumentation()
                    .targetContext

            val network =
                NetworkFactory(
                    context = context,
                    baseUrl =
                        BuildConfig.BACKEND_BASE_URL,
                    debug = true,
                )

            // 1. ?? Customer ???
            val loginResponse =
                network.api.demoLogin(
                    DemoLoginRequest(
                        BuildConfig.E2E_CUSTOMER_CODE
                    )
                )

            assertTrue(
                "demo-login HTTP ??",
                loginResponse.isSuccessful,
            )

            val loginEnvelope =
                requireNotNull(
                    loginResponse.body()
                )

            assertTrue(
                "demo-login envelope ??",
                loginEnvelope.success,
            )

            val session =
                requireNotNull(
                    loginEnvelope.data
                )

            assertEquals(
                "CUSTOMER",
                session.user.roleCode,
            )

            network.tokenStore.saveBlocking(
                AuthTokens(
                    accessToken =
                        session.accessToken,
                    refreshToken =
                        session.refreshToken,
                )
            )

            // 2. P0 ?? ACTIVE ?? ??
            val subscriptionsResponse =
                network.api.mySubscriptions()

            assertTrue(
                "subscription HTTP ??",
                subscriptionsResponse
                    .isSuccessful,
            )

            val subscriptions =
                requireNotNull(
                    requireNotNull(
                        subscriptionsResponse.body()
                    ).data
                )

            val subscription =
                requireNotNull(
                    subscriptions.items
                        .firstOrNull {
                            it.statusCode ==
                                "ACTIVE" &&
                                it.product.modelCode ==
                                P0_SUPPORTED_MODEL_CODE
                        }
                )

            // 3. ?? Inquiry 1? ??
            val createResponse =
                network.api.createInquiry(
                    idempotencyKey =
                        UUID.randomUUID()
                            .toString(),
                    body =
                        CreateInquiryRequest(
                            subscriptionId =
                                subscription
                                    .subscriptionId,
                            channelCode =
                                "MOBILE",
                            rawText =
                                "???? ????",
                            representativeSymptomCode =
                                "LOW_FLOW",
                            questionnaireSessionId =
                                null,
                        ),
                )

            assertTrue(
                "create inquiry HTTP ??",
                createResponse.isSuccessful,
            )

            val createEnvelope =
                requireNotNull(
                    createResponse.body()
                )

            assertTrue(
                "create inquiry envelope ??",
                createEnvelope.success,
            )

            val inquiry =
                requireNotNull(
                    createEnvelope.data
                )

            assertFalse(
                "?? Inquiry? replay?? ? ???.",
                inquiry.idempotentReplay,
            )

            // 4. ?? ?? ??
            val submitResponse =
                network.api.submitSymptom(
                    inquiryId =
                        inquiry.inquiryId,
                    idempotencyKey =
                        UUID.randomUUID()
                            .toString(),
                    body =
                        SubmitSymptomRequest(
                            stateVersion =
                                inquiry.stateVersion,
                        ),
                )

            assertTrue(
                "submit symptom HTTP ??",
                submitResponse.isSuccessful,
            )

            val submitEnvelope =
                requireNotNull(
                    submitResponse.body()
                )

            assertTrue(
                "submit symptom envelope ??",
                submitEnvelope.success,
            )

            // 5. ?? ?? ?? Snapshot ??
            val beforeResponse =
                network.api
                    .customerInquirySnapshot(
                        inquiry.inquiryId
                    )

            assertTrue(
                "before snapshot HTTP ??",
                beforeResponse.isSuccessful,
            )

            val beforeEnvelope =
                requireNotNull(
                    beforeResponse.body()
                )

            assertTrue(
                "before snapshot envelope ??",
                beforeEnvelope.success,
            )

            val before =
                requireNotNull(
                    beforeEnvelope.data
                )

            assertEquals(
                "QUESTIONNAIRE_IN_PROGRESS",
                before.statusCode,
            )

            assertTrue(
                "state_version? 1 ????? ???.",
                before.stateVersion >= 1,
            )

            val beforeActions =
                before.allowedActions
                    .map {
                        it.code
                            .trim()
                            .uppercase()
                    }

            assertTrue(
                "QUESTIONNAIRE ??? CANCEL_INQUIRY? ????.",
                InquiryActionLabels
                    .CANCEL_INQUIRY in
                    beforeActions,
            )

            // 6. ?? Backend cancel endpoint ??
            val cancelResponse =
                network.api.cancelInquiry(
                    inquiryId =
                        before.inquiryId,
                    idempotencyKey =
                        UUID.randomUUID()
                            .toString(),
                    body =
                        CancelInquiryRequest(
                            stateVersion =
                                before.stateVersion,
                            reasonCode =
                                "CUSTOMER_REQUEST",
                            reasonDetail =
                                null,
                        ),
                )

            assertTrue(
                "cancel inquiry HTTP ??",
                cancelResponse.isSuccessful,
            )

            val cancelEnvelope =
                requireNotNull(
                    cancelResponse.body()
                )

            assertTrue(
                "cancel inquiry envelope ??",
                cancelEnvelope.success,
            )

            val cancelled =
                requireNotNull(
                    cancelEnvelope.data
                )

            assertEquals(
                before.inquiryId,
                cancelled.inquiryId,
            )

            assertEquals(
                "CANCELLED",
                cancelled.state,
            )

            assertTrue(
                "?? ? state_version? ???? ???.",
                cancelled.stateVersion >
                    before.stateVersion,
            )

            // 7. ?? ? ?? Customer Snapshot ???
            val afterResponse =
                network.api
                    .customerInquirySnapshot(
                        inquiry.inquiryId
                    )

            assertTrue(
                "after snapshot HTTP ??",
                afterResponse.isSuccessful,
            )

            val afterEnvelope =
                requireNotNull(
                    afterResponse.body()
                )

            assertTrue(
                "after snapshot envelope ??",
                afterEnvelope.success,
            )

            val after =
                requireNotNull(
                    afterEnvelope.data
                )

            assertEquals(
                "CANCELLED",
                after.statusCode,
            )

            assertEquals(
                cancelled.stateVersion,
                after.stateVersion,
            )

            val afterActions =
                after.allowedActions
                    .map {
                        it.code
                            .trim()
                            .uppercase()
                    }

            assertFalse(
                "CANCELLED ???? CANCEL_INQUIRY? ?? ??? ? ???.",
                InquiryActionLabels
                    .CANCEL_INQUIRY in
                    afterActions,
            )

            // Token/Secret? ?? ???? ???.
            val evidence =
                listOf(
                    "subscription_id=" +
                        subscription
                            .subscriptionId,
                    "inquiry_id=" +
                        after.inquiryId,
                    "before_status=" +
                        before.statusCode,
                    "before_state_version=" +
                        before.stateVersion,
                    "before_allowed_actions=" +
                        beforeActions
                            .joinToString(","),
                    "cancel_state=" +
                        cancelled.state,
                    "cancel_state_version=" +
                        cancelled.stateVersion,
                    "cancel_idempotent_replay=" +
                        cancelled
                            .idempotentReplay,
                    "after_status=" +
                        after.statusCode,
                    "after_state_version=" +
                        after.stateVersion,
                    "after_allowed_actions=" +
                        afterActions
                            .ifEmpty {
                                listOf("NONE")
                            }
                            .joinToString(","),
                ).joinToString("|")

            Log.i(
                "WB_P0_CANCEL",
                evidence,
            )

            println(
                "WB_P0_CANCEL|$evidence"
            )
        }
}
