package com.skn29.watercare.customer

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.model.AuthTokens
import com.skn29.watercare.core.model.CreateInquiryRequest
import com.skn29.watercare.core.model.DemoLoginRequest
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
class CustomerSharedBackendSmokeEvidenceTest {
    @Test
    fun customerToBackendPostgresql_createSubmitSnapshot() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("runRemoteSmoke") == "true")

        val context =
            InstrumentationRegistry.getInstrumentation().targetContext

        val network = NetworkFactory(
            context = context,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = true,
        )

        val loginResponse = network.api.demoLogin(
            DemoLoginRequest(BuildConfig.E2E_CUSTOMER_CODE)
        )
        assertTrue(loginResponse.isSuccessful)
        val loginEnvelope = requireNotNull(loginResponse.body())
        assertTrue(loginEnvelope.success)
        val session = requireNotNull(loginEnvelope.data)
        assertEquals("CUSTOMER", session.user.roleCode)

        network.tokenStore.saveBlocking(
            AuthTokens(
                accessToken = session.accessToken,
                refreshToken = session.refreshToken,
            )
        )

        val subscriptionsResponse = network.api.mySubscriptions()
        assertTrue(subscriptionsResponse.isSuccessful)
        val subscriptions =
            requireNotNull(requireNotNull(subscriptionsResponse.body()).data)

        val subscription = requireNotNull(
            subscriptions.items.firstOrNull {
                it.statusCode == "ACTIVE" &&
                    it.product.modelCode == P0_SUPPORTED_MODEL_CODE
            }
        )

        val detailResponse =
            network.api.mySubscription(subscription.subscriptionId)
        assertTrue(detailResponse.isSuccessful)
        assertTrue(requireNotNull(detailResponse.body()).success)

        val createResponse = network.api.createInquiry(
            idempotencyKey = UUID.randomUUID().toString(),
            body = CreateInquiryRequest(
                subscriptionId = subscription.subscriptionId,
                channelCode = "MOBILE",
                rawText = "출수량이 줄었어요",
                representativeSymptomCode = "LOW_FLOW",
                questionnaireSessionId = null,
            ),
        )
        assertTrue(createResponse.isSuccessful)
        val createEnvelope = requireNotNull(createResponse.body())
        assertTrue(createEnvelope.success)
        val inquiry = requireNotNull(createEnvelope.data)
        assertFalse(inquiry.idempotentReplay)

        val submitResponse = network.api.submitSymptom(
            inquiryId = inquiry.inquiryId,
            idempotencyKey = UUID.randomUUID().toString(),
            body = SubmitSymptomRequest(
                stateVersion = inquiry.stateVersion,
            ),
        )
        assertTrue(submitResponse.isSuccessful)
        val submitEnvelope = requireNotNull(submitResponse.body())
        assertTrue(submitEnvelope.success)
        val submitted = requireNotNull(submitEnvelope.data)

        assertEquals(inquiry.inquiryId, submitted.inquiryId)
        assertTrue(submitted.stateVersion > inquiry.stateVersion)

        val snapshotResponse =
            network.api.customerInquirySnapshot(inquiry.inquiryId)
        assertTrue(snapshotResponse.isSuccessful)

        val snapshotEnvelope = requireNotNull(snapshotResponse.body())
        assertTrue(snapshotEnvelope.success)
        val snapshot = requireNotNull(snapshotEnvelope.data)

        assertEquals(inquiry.inquiryId, snapshot.inquiryId)
        assertEquals(subscription.subscriptionId, snapshot.subscriptionId)
        assertEquals(P0_SUPPORTED_MODEL_CODE, snapshot.product.modelCode)
        assertEquals(submitted.stateVersion, snapshot.stateVersion)

        val allowed = snapshot.allowedActions
            .map { it.code }
            .joinToString(",")

        val evidence = listOf(
            "subscription_id=${subscription.subscriptionId}",
            "inquiry_id=${snapshot.inquiryId}",
            "status=${snapshot.statusCode}",
            "state_version=${snapshot.stateVersion}",
            "allowed_actions=${allowed.ifBlank { "NONE" }}",
            "corr_create=${requireNotNull(createEnvelope.metadata?.correlationId)}",
            "corr_submit=${requireNotNull(submitEnvelope.metadata?.correlationId)}",
            "corr_snapshot=${requireNotNull(snapshotEnvelope.metadata?.correlationId)}",
        ).joinToString("|")

        Log.i("WB_SECTION5", evidence)
        println("WB_SECTION5|$evidence")
    }
}