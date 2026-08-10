package com.skn29.watercare.customer

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.SessionResponse
import com.skn29.watercare.core.model.SubscriptionListDataDto
import com.skn29.watercare.core.model.SymptomIntakeRequest
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CustomerRemoteBackendSmokeTest {
    @Test
    fun login_subscriptionDetail_createAndSubmit_realBackend() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("runRemoteSmoke") == "true")

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        WaterCareCore.initialize(
            context = context,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = true,
            customerCareMode = "REMOTE",
            demoSubscriptionId = "",
        )

        val login = WaterCareCore.authRepository.demoLogin("DEMO-CUSTOMER-001")
        assertTrue(login is ApiResult.Success<*>)
        val session = (login as ApiResult.Success<SessionResponse>).value
        assertEquals("CUSTOMER", session.user.roleCode)

        val subscriptions = WaterCareCore.subscriptionRepository.list()
        assertTrue(subscriptions is ApiResult.Success<*>)
        val list = (subscriptions as ApiResult.Success<SubscriptionListDataDto>).value
        val target = list.items.firstOrNull {
            it.statusCode == "ACTIVE" &&
                it.product.modelCode == P0_SUPPORTED_MODEL_CODE
        }
        assumeTrue(target != null)

        val subscription = requireNotNull(target)
        val detail = WaterCareCore.subscriptionRepository.detail(subscription.subscriptionId)
        assertTrue(detail is ApiResult.Success<*>)

        val intake = WaterCareCore.customerCareRepository.submitIntake(
            SymptomIntakeRequest(
                subscriptionId = subscription.subscriptionId,
                symptomCodes = listOf("LOW_FLOW"),
                rawText = "출수량이 줄었어요",
                occurrenceCondition = "냉수 출수 시",
                displayText = null,
                entryMode = "ADHOC_INQUIRY",
                idempotencyKey = "instrumentation-managed-by-repository",
            )
        )

        assertTrue(intake is ApiResult.Success<*>)
        val submission = (intake as ApiResult.Success<IntakeSubmission>).value
        assertTrue(submission.inquiryId.isNotBlank())
        assertTrue(submission.inquiryCode.isNotBlank())
        assertTrue(submission.stateVersion != null)
        assertTrue(submission.statusCode?.isNotBlank() == true)
    }
}
