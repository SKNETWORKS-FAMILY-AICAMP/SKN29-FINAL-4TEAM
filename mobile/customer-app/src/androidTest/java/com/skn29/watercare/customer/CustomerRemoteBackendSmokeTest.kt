package com.skn29.watercare.customer

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
import com.skn29.watercare.core.model.P0_SYNTHETIC_CUSTOMER_LOGIN_CODE
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

        val login = WaterCareCore.authRepository.demoLogin(P0_SYNTHETIC_CUSTOMER_LOGIN_CODE)
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

    @Test
    fun guidanceRemoteMode_callsPublishedCustomerRoute() = runBlocking {
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
        val login = WaterCareCore.authRepository.demoLogin(
            P0_SYNTHETIC_CUSTOMER_LOGIN_CODE
        )
        assertTrue(login is ApiResult.Success<*>)

        val guidance = WaterCareCore.customerCareRepository.getGuidance(
            inquiryId = "00000000-0000-4000-8000-000000000301",
            scenario = MockScenario.NORMAL,
        )

        when (guidance) {
            is ApiResult.Success ->
                assertEquals(
                    "00000000-0000-4000-8000-000000000301",
                    guidance.value.inquiryId,
                )
            is ApiResult.Failure -> {
                assertTrue(
                    guidance.code != "GUIDANCE_ROUTE_UNAVAILABLE"
                )
                assertTrue(
                    guidance.code in setOf(
                        "AI_GUIDANCE_NOT_READY",
                        "RESOURCE_NOT_FOUND",
                        "HTTP_404",
                    )
                )
            }
        }
    }

    @Test
    fun dangerGuidanceAndConsultationRequest_useRealBackend() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("runRemoteP0") == "true")

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        WaterCareCore.initialize(
            context = context,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = true,
            customerCareMode = "REMOTE",
            demoSubscriptionId = "",
        )

        val login = WaterCareCore.authRepository.demoLogin(
            P0_SYNTHETIC_CUSTOMER_LOGIN_CODE
        )
        assertTrue(login is ApiResult.Success<*>)

        val subscriptions = WaterCareCore.subscriptionRepository.list()
        assertTrue(subscriptions is ApiResult.Success<*>)
        val target = (
            subscriptions as ApiResult.Success<SubscriptionListDataDto>
        ).value.items.firstOrNull {
            it.statusCode == "ACTIVE" &&
                it.product.modelCode == P0_SUPPORTED_MODEL_CODE
        }
        assertTrue(
            "ACTIVE WPUJAC104DWH subscription is required for P0.",
            target != null,
        )

        val intake = WaterCareCore.customerCareRepository.submitIntake(
            SymptomIntakeRequest(
                subscriptionId = requireNotNull(target).subscriptionId,
                symptomCodes = listOf("LEAK"),
                rawText = "제품 하단에서 물이 새고 전원선 주변까지 젖어 있습니다.",
                occurrenceCondition = "제품 사용 직후에도 누수가 계속됨",
                displayText = null,
                entryMode = "ADHOC_INQUIRY",
                idempotencyKey = "instrumentation-managed-by-repository",
            )
        )
        assertTrue(intake is ApiResult.Success<*>)
        val inquiry = (intake as ApiResult.Success<IntakeSubmission>).value

        val snapshotResult =
            WaterCareCore.customerInquiryRepository.snapshot(inquiry.inquiryId)
        assertTrue(snapshotResult is ApiResult.Success<*>)
        val snapshot = (
            snapshotResult as ApiResult.Success<CustomerInquirySnapshot>
        ).value
        assertEquals(inquiry.inquiryId, snapshot.inquiryId)
        assertEquals("CONSULTATION_REQUIRED", snapshot.statusCode)
        assertTrue(
            snapshot.allowedActions.any {
                it.normalizedCode == InquiryActionLabels.REQUEST_CONSULTATION
            }
        )

        val guidanceResult =
            WaterCareCore.customerInquiryRepository.guidance(inquiry.inquiryId)
        assertTrue(guidanceResult is ApiResult.Success<*>)
        val guidance = (guidanceResult as ApiResult.Success<GuidanceData>).value
        assertEquals(inquiry.inquiryId, guidance.inquiryId)
        assertEquals("danger", guidance.riskLevel.lowercase())
        assertEquals("TOTAL_STOP", guidance.usageGuidanceStatus.uppercase())
        assertTrue(guidance.requiresConsultation)
        assertTrue(guidance.evidence.isEmpty())

        val requestResult =
            WaterCareCore.customerInquiryRepository.requestConsultation(
                inquiryId = inquiry.inquiryId,
                stateVersion = snapshot.stateVersion,
            )
        assertTrue(requestResult is ApiResult.Success<*>)
        val requested = (
            requestResult as ApiResult.Success<RequestConsultationResult>
        ).value
        assertEquals(inquiry.inquiryId, requested.inquiryId)
        assertEquals("CONSULTATION_REQUIRED", requested.statusCode)
        assertTrue(requested.stateVersion > snapshot.stateVersion)

        println("P0_DEVICE_INQUIRY_ID=${inquiry.inquiryId}")
        println("P0_DEVICE_STATE_VERSION=${requested.stateVersion}")
    }

    @Test
    fun completedInquiryFinalState_usesRealBackend() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("runRemoteP0Final") == "true")
        val inquiryId = requireNotNull(args.getString("p0InquiryId")) {
            "p0InquiryId instrumentation argument is required."
        }.trim()
        require(inquiryId.isNotEmpty()) {
            "p0InquiryId instrumentation argument must not be blank."
        }

        val context = InstrumentationRegistry.getInstrumentation().targetContext
        WaterCareCore.initialize(
            context = context,
            baseUrl = BuildConfig.BACKEND_BASE_URL,
            debug = true,
            customerCareMode = "REMOTE",
            demoSubscriptionId = "",
        )
        val login = WaterCareCore.authRepository.demoLogin(
            P0_SYNTHETIC_CUSTOMER_LOGIN_CODE
        )
        assertTrue(login is ApiResult.Success<*>)

        val snapshotResult =
            WaterCareCore.customerInquiryRepository.snapshot(inquiryId)
        assertTrue(snapshotResult is ApiResult.Success<*>)
        val snapshot = (
            snapshotResult as ApiResult.Success<CustomerInquirySnapshot>
        ).value
        assertEquals(inquiryId, snapshot.inquiryId)
        assertEquals("COMPLETION_PENDING", snapshot.statusCode)

        val guidanceResult =
            WaterCareCore.customerInquiryRepository.guidance(inquiryId)
        assertTrue(guidanceResult is ApiResult.Success<*>)
        val guidance = (guidanceResult as ApiResult.Success<GuidanceData>).value
        assertEquals(inquiryId, guidance.inquiryId)
        assertEquals("danger", guidance.riskLevel.lowercase())
        assertEquals("TOTAL_STOP", guidance.usageGuidanceStatus.uppercase())
        assertTrue(guidance.evidence.isEmpty())

        println("P0_DEVICE_FINAL_INQUIRY_ID=$inquiryId")
        println("P0_DEVICE_FINAL_STATUS=${snapshot.statusCode}")
        println("P0_DEVICE_FINAL_STATE_VERSION=${snapshot.stateVersion}")
    }
}
