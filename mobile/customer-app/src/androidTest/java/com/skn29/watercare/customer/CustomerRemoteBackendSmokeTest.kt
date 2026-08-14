package com.skn29.watercare.customer

import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.GuidanceData
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.P0_SUPPORTED_MODEL_CODE
import com.skn29.watercare.core.model.RequestConsultationResult
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

        val login = WaterCareCore.authRepository.demoLogin(BuildConfig.E2E_CUSTOMER_CODE)
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

        Log.i(
            "CustomerG1SubmitSmoke",
            "inquiry_id=${submission.inquiryId} " +
                "inquiry_code=${submission.inquiryCode} " +
                "status=${submission.statusCode} " +
                "state_version=${submission.stateVersion} " +
                "idempotent_replay=${submission.idempotentReplay}",
        )
    }

    @Test
    fun customerGuidanceAndConsultationRequest_realBackend() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("runRemoteSmoke") == "true")
        val inquiryId = args.getString("guidanceInquiryId").orEmpty().trim()
        assertTrue(
            "runRemoteSmoke=true requires guidanceInquiryId",
            inquiryId.isNotEmpty(),
        )

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        WaterCareCore.initialize(
            context = context,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = true,
            customerCareMode = "REMOTE",
            demoSubscriptionId = "",
        )

        val login = WaterCareCore.authRepository.demoLogin(BuildConfig.E2E_CUSTOMER_CODE)
        assertTrue(login is ApiResult.Success<*>)

        val guidance = WaterCareCore.customerCareRepository.getGuidance(
            inquiryId = inquiryId,
            scenario = MockScenario.NORMAL,
        )

        assertTrue(guidance is ApiResult.Success<*>)
        val success = guidance as ApiResult.Success<GuidanceData>
        assertEquals(inquiryId, success.value.inquiryId)
        assertTrue(success.value.stateVersion >= 1)
        assertTrue(success.value.usageGuidanceMessage.isNotBlank())
        assertTrue(success.value.safeActions.isNotEmpty())
        assertTrue(success.value.evidence.isEmpty())

        val before = WaterCareCore.customerInquiryRepository.snapshot(inquiryId)
        assertTrue(before is ApiResult.Success<*>)
        val beforeSnapshot =
            (before as ApiResult.Success<CustomerInquirySnapshot>).value
        assertEquals(inquiryId, beforeSnapshot.inquiryId)
        assertTrue(
            beforeSnapshot.allowedActions.any {
                it.normalizedCode == InquiryActionLabels.REQUEST_CONSULTATION
            }
        )

        val requested = WaterCareCore.customerInquiryRepository.requestConsultation(
            inquiryId = inquiryId,
            stateVersion = beforeSnapshot.stateVersion,
        )
        assertTrue(requested is ApiResult.Success<*>)
        val requestResult =
            (requested as ApiResult.Success<RequestConsultationResult>).value
        assertEquals(inquiryId, requestResult.inquiryId)
        assertEquals("CONSULTATION_REQUIRED", requestResult.statusCode)
        assertTrue(requestResult.stateVersion >= beforeSnapshot.stateVersion)

        val after = WaterCareCore.customerInquiryRepository.snapshot(inquiryId)
        assertTrue(after is ApiResult.Success<*>)
        val afterSnapshot =
            (after as ApiResult.Success<CustomerInquirySnapshot>).value
        assertEquals(requestResult.statusCode, afterSnapshot.statusCode)
        assertEquals(requestResult.stateVersion, afterSnapshot.stateVersion)

        Log.i(
            "CustomerG2G3Smoke",
            "inquiry_id=$inquiryId " +
                "before_status=${beforeSnapshot.statusCode} " +
                "before_version=${beforeSnapshot.stateVersion} " +
                "after_status=${afterSnapshot.statusCode} " +
                "after_version=${afterSnapshot.stateVersion} " +
                "idempotent_replay=${requestResult.idempotentReplay}",
        )
    }
}
