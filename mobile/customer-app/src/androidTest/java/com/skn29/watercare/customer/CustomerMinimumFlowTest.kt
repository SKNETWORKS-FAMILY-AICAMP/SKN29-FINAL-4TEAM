package com.skn29.watercare.customer

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.skn29.watercare.core.model.ActiveInquirySummary
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.GuidanceDisplayModel
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.ProductSummary
import com.skn29.watercare.core.model.RiskLevel
import com.skn29.watercare.core.model.UsageGuidanceStatus
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.customer.feature.customer.guidance.GuidanceContent
import com.skn29.watercare.customer.feature.customer.home.CustomerHomeContent
import com.skn29.watercare.customer.feature.customer.home.CustomerHomeUiState
import com.skn29.watercare.customer.feature.customer.intake.IntakeErrorKind
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeContent
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeUiState
import com.skn29.watercare.customer.testing.ComposeTestActivity
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CustomerMinimumFlowTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<ComposeTestActivity>()

    @Test
    fun offlinePreview_opensCust01AndCust02() {
        composeRule.setContent {
            var showIntake by remember { mutableStateOf(false) }

            WaterCareTheme {
                if (showIntake) {
                    SymptomIntakeContent(
                        state = SymptomIntakeUiState(),
                        onBack = { showIntake = false },
                        onEntryModeChange = {},
                        onToggleSymptom = {},
                        onRawTextChange = {},
                        onOccurrenceConditionChange = {},
                        onDisplayTextChange = {},
                        onScenarioChange = {},
                        onRetry = {},
                        onSubmit = {},
                    )
                } else {
                    CustomerHomeContent(
                        state = sampleHomeState(),
                        onStartIntake = { showIntake = true },
                        onOpenGuidance = { _, _ -> },
                        onRetry = {},
                        onLogout = {},
                    )
                }
            }
        }

        composeRule.waitForIdle()

        composeRule.onNodeWithTag("startIntake")
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()

        composeRule.waitForIdle()

        composeRule.onNodeWithTag("submitIntake")
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    fun dangerGuidance_hidesResolvedAction() {
        composeRule.setContent {
            var showDangerGuidance by remember { mutableStateOf(false) }

            WaterCareTheme {
                if (showDangerGuidance) {
                    GuidanceContent(
                        guidance = dangerGuidance(),
                        noEvidence = false,
                        onRetry = {},
                        onRequestConsultation = {},
                        onDone = {},
                    )
                } else {
                    CustomerHomeContent(
                        state = sampleHomeState(),
                        onStartIntake = {},
                        onOpenGuidance = { _, scenario ->
                            if (scenario == MockScenario.DANGER) {
                                showDangerGuidance = true
                            }
                        },
                        onRetry = {},
                        onLogout = {},
                    )
                }
            }
        }

        composeRule.waitForIdle()

        composeRule.onNodeWithTag("scenario_DANGER")
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()

        composeRule.waitForIdle()

        composeRule.onNodeWithTag("requestConsultation")
            .assertIsDisplayed()

        val resolvedActionDoesNotExist = runCatching {
            composeRule.onNodeWithTag("resolvedAction").fetchSemanticsNode()
        }.isFailure

        assertTrue(
            "위험 안내 화면에서는 해결 처리 버튼이 표시되면 안 됩니다.",
            resolvedActionDoesNotExist,
        )
    }

    @Test
    fun conflict_showsOnlySupportedSubmitRetryAction() {
        var retried = false

        composeRule.setContent {
            WaterCareTheme {
                SymptomIntakeContent(
                    state = SymptomIntakeUiState(
                        rawText = "충돌 테스트 입력",
                        globalError = "최신 상태를 확인해 주세요.",
                        errorKind = IntakeErrorKind.CONFLICT,
                        conflictStatus = "DRAFT",
                        conflictStateVersion = 2,
                        conflictAllowedActions = listOf(
                            AllowedAction(code = "SUBMIT_SYMPTOM"),
                            AllowedAction(code = "INTERNAL_ONLY_ACTION"),
                        ),
                    ),
                    onBack = {},
                    onEntryModeChange = {},
                    onToggleSymptom = {},
                    onRawTextChange = {},
                    onOccurrenceConditionChange = {},
                    onDisplayTextChange = {},
                    onScenarioChange = {},
                    onRetry = { retried = true },
                    onSubmit = {},
                )
            }
        }

        composeRule.waitForIdle()

        composeRule.onNodeWithTag("retrySubmitAfterConflict")
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()

        val unsupportedActionDoesNotExist = runCatching {
            composeRule.onNodeWithText("INTERNAL_ONLY_ACTION")
                .fetchSemanticsNode()
        }.isFailure

        assertTrue(
            "지원하지 않는 Backend Action은 고객 화면에 표시되면 안 됩니다.",
            unsupportedActionDoesNotExist,
        )

        composeRule.onNodeWithTag("submitIntake")
            .performScrollTo()
            .assertIsNotEnabled()

        assertTrue(
            "SUBMIT_SYMPTOM이 허용된 충돌에서는 명시적 재시도만 실행되어야 합니다.",
            retried,
        )
    }

    private fun sampleHomeState() = CustomerHomeUiState(
        loading = false,
        home = CustomerHomeData(
            subscriptionId = TEST_SUBSCRIPTION_ID,
            product = ProductSummary(
                productId = "00000000-0000-4000-8000-000000000201",
                modelCode = "WPUJAC104DWH",
                modelName = "WPU-JAC104D",
                serialNo = "SYN-JAC104-002",
                managementTypeCode = "VISIT_CARE",
                managementTypeLabel = "방문 관리",
                isSynthetic = true,
            ),
            questionnaireStatus = "사전 문진 가능",
            nextCareOn = "2026-08-04",
            activeInquiry = ActiveInquirySummary(
                inquiryId = TEST_INQUIRY_ID,
                inquiryCode = "DEMO-INQ-002",
                statusCode = "AI_GUIDANCE",
                statusLabel = "AI 안내 확인",
            ),
        ),
        backendAvailable = false,
        offlinePreview = true,
    )

    private fun dangerGuidance() = GuidanceDisplayModel(
        inquiryId = TEST_INQUIRY_ID,
        inquiryCode = "DEMO-DANGER-001",
        symptomSummary = "제품 하단 누수 위험",
        riskLevel = RiskLevel.DANGER,
        usageStatus = UsageGuidanceStatus.TOTAL_STOP,
        usageMessage = "제품 사용을 즉시 중지하세요.",
        restrictedFunctions = listOf("제품 전체 사용"),
        safeActions = listOf("제품과 거리를 유지하세요."),
        escalationConditions = listOf("상담을 요청하세요."),
        prohibitedActions = listOf("제품 분해"),
        nextAction = "즉시 상담 요청",
        requiresConsultation = true,
        evidence = emptyList(),
        allowedActions = listOf("REQUEST_CONSULTATION"),
    )

    companion object {
        private const val TEST_SUBSCRIPTION_ID =
            "00000000-0000-4000-8000-000000000101"
        private const val TEST_INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"
    }
}
