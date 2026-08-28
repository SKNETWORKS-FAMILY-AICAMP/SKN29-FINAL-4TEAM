package com.skn29.watercare.customer


import android.content.pm.ActivityInfo
import android.content.res.Configuration
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.junit4.v2.createEmptyComposeRule
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.ActiveInquirySummary
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.GuidanceDisplayModel
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.ProductSummary
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.core.model.RiskLevel
import com.skn29.watercare.core.model.UsageGuidanceStatus
import com.skn29.watercare.core.ui.theme.WaterCareTheme
import com.skn29.watercare.customer.feature.customer.guidance.CustomerResolutionSection
import com.skn29.watercare.customer.feature.customer.guidance.CustomerResolutionUiState
import com.skn29.watercare.customer.feature.customer.guidance.GuidanceContent
import com.skn29.watercare.customer.feature.shared.WaterCareScreen
import com.skn29.watercare.customer.feature.customer.home.CustomerHomeContent
import com.skn29.watercare.customer.feature.customer.home.CustomerHomeUiState
import com.skn29.watercare.customer.feature.customer.intake.IntakeErrorKind
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeContent
import com.skn29.watercare.customer.feature.customer.intake.SymptomIntakeUiState
import com.skn29.watercare.customer.feature.shared.WorkflowActionButton
import org.junit.Assert.assertTrue
import com.skn29.watercare.customer.testing.ComposeTestActivity
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith


private class ManualComposeTestScope(
    private val delegate: ComposeTestRule,
    private val scenario: ActivityScenario<ComposeTestActivity>,
) : ComposeTestRule by delegate {
    fun setContent(
        content: @Composable () -> Unit,
    ) {
        if (scenario.state != Lifecycle.State.RESUMED) {
            scenario.moveToState(Lifecycle.State.RESUMED)
        }

        scenario.onActivity { activity ->
            activity.setContent {
                content()
            }
        }

        delegate.waitForIdle()
    }
    fun requestOrientation(
        orientation: Int,
    ) {
        scenario.onActivity { activity ->
            activity.requestedOrientation = orientation
        }
        Thread.sleep(1200)
    }

    fun currentOrientation(): Int {
        if (scenario.state != Lifecycle.State.RESUMED) {
            scenario.moveToState(Lifecycle.State.RESUMED)
        }

        var orientation = Configuration.ORIENTATION_UNDEFINED

        scenario.onActivity { activity ->
            orientation =
                activity.resources.configuration.orientation
        }

        return orientation
    }
}

private fun androidx.compose.ui.test.SemanticsNodeInteraction.assertDoesNotExistCompat() {
    assertTrue(
        "화면에 존재하지 않아야 하는 UI가 표시되었습니다.",
        runCatching {
            fetchSemanticsNode()
        }.isFailure,
    )
}
@RunWith(AndroidJUnit4::class)
class CustomerMinimumFlowTest {
    @get:Rule
    val composeTestRule = createEmptyComposeRule()

    private fun runManualComposeUiTest(
        block: ManualComposeTestScope.() -> Unit,
    ) {
        val scenario = ActivityScenario.launch(ComposeTestActivity::class.java)
        try {
            if (scenario.state != Lifecycle.State.RESUMED) {
                scenario.moveToState(Lifecycle.State.RESUMED)
            }

            ManualComposeTestScope(
                delegate = composeTestRule,
                scenario = scenario,
            ).block()
        } finally {
            scenario.close()
        }
    }
    @Test
    @OptIn(ExperimentalTestApi::class)
    fun offlinePreview_currentDashboardOpensIntake() = runManualComposeUiTest {
        setContent {
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
                        state = sampleHomeState(
                            activeInquiry = null,
                        ),
                        onStartIntake = { showIntake = true },
                        onOpenGuidance = { _, _ -> },
                        onRetry = {},
                        onLogout = {},
                    )
                }
            }
        }

        waitForIdle()

        onNodeWithTag("customerProblemCheck")
            .performScrollTo()
            .assertIsDisplayed()

        onNodeWithTag("problemCheckArrow")
            .assertIsDisplayed()
            .performClick()

        waitForIdle()

        onNodeWithTag("submitIntake")
            .performScrollTo()
            .assertIsDisplayed()
    }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun lowFlowQuickAction_withoutActiveInquiry_selectsLowFlowAndSubmitsDetail() =
        runManualComposeUiTest {
            var receivedPreset:
                SymptomTopic? = null

            var submitted = false

            var submittedSymptoms:
                Set<SymptomTopic> =
                emptySet()

            var submittedRawText = ""

            setContent {
                var showIntake by remember {
                    mutableStateOf(false)
                }

                var intakeState by remember {
                    mutableStateOf(
                        SymptomIntakeUiState()
                    )
                }

                WaterCareTheme {
                    if (showIntake) {
                        SymptomIntakeContent(
                            state = intakeState,
                            onBack = {
                                showIntake = false
                            },
                            onEntryModeChange = {
                                value ->
                                intakeState =
                                    intakeState.copy(
                                        entryMode =
                                            value,
                                    )
                            },
                            onToggleSymptom = {
                                topic ->
                                val current =
                                    intakeState
                                        .selectedSymptoms

                                intakeState =
                                    intakeState.copy(
                                        selectedSymptoms =
                                            if (
                                                topic in
                                                    current
                                            ) {
                                                current -
                                                    topic
                                            } else {
                                                current +
                                                    topic
                                            },
                                    )
                            },
                            onRawTextChange = {
                                value ->
                                intakeState =
                                    intakeState.copy(
                                        rawText =
                                            value,
                                    )
                            },
                            onOccurrenceConditionChange = {
                                value ->
                                intakeState =
                                    intakeState.copy(
                                        occurrenceCondition =
                                            value,
                                    )
                            },
                            onDisplayTextChange = {
                                value ->
                                intakeState =
                                    intakeState.copy(
                                        displayText =
                                            value,
                                    )
                            },
                            onScenarioChange = {
                                value ->
                                intakeState =
                                    intakeState.copy(
                                        forcedScenario =
                                            value,
                                    )
                            },
                            onRetry = {},
                            onSubmit = {
                                submitted = true

                                submittedSymptoms =
                                    intakeState
                                        .selectedSymptoms

                                submittedRawText =
                                    intakeState.rawText
                            },
                        )
                    } else {
                        val homeState =
                            sampleHomeState(
                                activeInquiry = null,
                            ).copy(
                                offlinePreview = false,
                                customerCareMode =
                                    CustomerCareMode
                                        .REMOTE,
                                backendAvailable = true,
                                intakeAvailable = true,
                            )

                        CustomerHomeContent(
                            state = homeState,
                            onStartIntake = {
                                showIntake = true
                            },
                            onStartIntakePreset = {
                                    _,
                                    topic,
                                    _,
                                ->
                                receivedPreset =
                                    topic

                                intakeState =
                                    SymptomIntakeUiState(
                                        selectedSymptoms =
                                            setOf(topic),
                                        rawText = "",
                                    )

                                showIntake = true
                            },
                            onOpenGuidance =
                                { _, _ -> },
                            onRetry = {},
                            onLogout = {},
                        )
                    }
                }
            }

            waitForIdle()

            onNodeWithText(
                "물이 약해요"
            )
                .performScrollTo()
                .assertIsDisplayed()
                .performClick()

            waitForIdle()

            assertTrue(
                "빠른 버튼은 LOW_FLOW를 전달해야 합니다.",
                receivedPreset ==
                    SymptomTopic.LOW_FLOW,
            )

            onNodeWithText(
                "물이 약해요"
            )
                .assertIsDisplayed()
                .assertIsSelected()

            onNodeWithTag("rawText")
                .performScrollTo()
                .assertIsDisplayed()
                .performTextInput(
                    "어제부터 물이 평소보다 약하게 나와요"
                )

            waitForIdle()

            onNodeWithTag(
                "submitIntake"
            )
                .performScrollTo()
                .assertIsDisplayed()
                .performClick()

            waitForIdle()

            assertTrue(
                "접수 버튼이 submit callback을 실행해야 합니다.",
                submitted,
            )

            assertTrue(
                "접수 시 LOW_FLOW가 유지되어야 합니다.",
                SymptomTopic.LOW_FLOW in
                    submittedSymptoms,
            )

            assertTrue(
                "입력한 상세 내용이 접수 데이터에 유지되어야 합니다.",
                submittedRawText ==
                    "어제부터 물이 평소보다 약하게 나와요",
            )
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun symptomIntake_portraitAndLandscape_keepsFullWidth() =
        runManualComposeUiTest {
            fun renderIntake() {
                setContent {
                    WaterCareTheme {
                        SymptomIntakeContent(
                            state = SymptomIntakeUiState(),
                            onBack = {},
                            onEntryModeChange = {},
                            onToggleSymptom = {},
                            onRawTextChange = {},
                            onOccurrenceConditionChange = {},
                            onDisplayTextChange = {},
                            onScenarioChange = {},
                            onRetry = {},
                            onSubmit = {},
                        )
                    }
                }
            }

            fun assertFullWidthLayout() {
                waitForIdle()

                val heroNode =
                    onNodeWithTag("intakeHero")
                        .assertIsDisplayed()

                val heroWidth =
                    heroNode
                        .fetchSemanticsNode()
                        .boundsInRoot
                        .width

                val inputNode =
                    onNodeWithTag("rawText")
                        .performScrollTo()
                        .assertIsDisplayed()

                waitForIdle()

                val inputWidth =
                    inputNode
                        .fetchSemanticsNode()
                        .boundsInRoot
                        .width

                val difference =
                    if (heroWidth >= inputWidth) {
                        heroWidth - inputWidth
                    } else {
                        inputWidth - heroWidth
                    }

                assertTrue(
                    "Hero와 입력 영역 폭이 일치하지 않습니다. hero=$heroWidth input=$inputWidth",
                    difference <= 2f,
                )
            }

            try {
                requestOrientation(
                    ActivityInfo.SCREEN_ORIENTATION_PORTRAIT,
                )
                renderIntake()

                assertTrue(
                    currentOrientation() ==
                        Configuration.ORIENTATION_PORTRAIT,
                )
                assertFullWidthLayout()

                requestOrientation(
                    ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE,
                )
                renderIntake()

                assertTrue(
                    currentOrientation() ==
                        Configuration.ORIENTATION_LANDSCAPE,
                )
                assertFullWidthLayout()
            } finally {
                requestOrientation(
                    ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED,
                )
            }
        }
    @Test
    @OptIn(ExperimentalTestApi::class)
    fun mobileG3_iac425AndIac606_disableIntakeOnCustomerUi() =
        runManualComposeUiTest {
            val blockedModels = listOf(
                "WPUIAC425SNW",
                "WPUIAC606SNW",
            )

            blockedModels.forEach { modelCode ->
                var intakeStarted = false

                setContent {
                    val baseState =
                        sampleHomeState(
                            activeInquiry = null,
                        )
                    val baseHome =
                        requireNotNull(baseState.home)

                    WaterCareTheme {
                        CustomerHomeContent(
                            state =
                                baseState.copy(
                                    offlinePreview = false,
                                    customerCareMode =
                                        CustomerCareMode.REMOTE,
                                    backendAvailable = true,
                                    home =
                                        baseHome.copy(
                                            product =
                                                baseHome.product.copy(
                                                    modelCode = modelCode,
                                                    modelName = modelCode,
                                                ),
                                            activeInquiry = null,
                                        ),
                                    intakeAvailable = false,
                                    intakeUnavailableReason =
                                        "이 정수기는 현재 문의 기능을 이용할 수 없어요.",
                                ),
                            onStartIntake = {
                                intakeStarted = true
                            },
                            onOpenGuidance = { _, _ -> },
                            onRetry = {},
                            onLogout = {},
                        )
                    }
                }

                waitForIdle()

                onNodeWithTag("customerProblemCheck")
                    .performScrollTo()
                    .assertIsDisplayed()

                onNodeWithText(
                    "이 정수기는 현재 문의 기능을 이용할 수 없어요."
                )
                    .performScrollTo()
                    .assertIsDisplayed()

                onNodeWithTag("problemCheckArrow")
                    .assertDoesNotExistCompat()

                onNodeWithText("물이 약해요")
                    .assertDoesNotExistCompat()

                onNodeWithText("누수가 보여요")
                    .assertDoesNotExistCompat()

                assertTrue(
                    "$modelCode must not enter intake UI",
                    !intakeStarted,
                )
            }
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun homeLoading_showsCustomerFriendlyProgress() =
        runManualComposeUiTest {
            setContent {
                WaterCareTheme {
                    CustomerHomeContent(
                        state = sampleHomeState(
                            activeInquiry = null,
                        ).copy(
                            loading = true,
                            home = null,
                            error = null,
                        ),
                        onStartIntake = {},
                        onOpenGuidance = { _, _ -> },
                        onRetry = {},
                        onLogout = {},
                    )
                }
            }

            waitForIdle()

            onNodeWithText("정수기 정보를 불러오고 있어요")
                .assertIsDisplayed()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun homeError_hidesTechnicalMessageAndShowsCustomerCopy() =
        runManualComposeUiTest {
            setContent {
                WaterCareTheme {
                    CustomerHomeContent(
                        state = sampleHomeState(
                            activeInquiry = null,
                        ).copy(
                            loading = false,
                            home = null,
                            error = "Backend API Remote timeout",
                        ),
                        onStartIntake = {},
                        onOpenGuidance = { _, _ -> },
                        onRetry = {},
                        onLogout = {},
                    )
                }
            }

            waitForIdle()

            onNodeWithText(
                "정수기 정보를 가져오지 못했어요. 잠시 후 다시 확인해주세요."
            ).assertIsDisplayed()

            onNodeWithText("Backend API Remote timeout")
                .assertDoesNotExistCompat()
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun dangerGuidance_keepsSafetyAndHidesInternalEmptyUi() =
        runManualComposeUiTest {
            setContent {
                WaterCareTheme {
                    WaterCareScreen(
                        title = "Guidance test",
                    ) {
                        GuidanceContent(
                            guidance = dangerGuidance(),
                            noEvidence = false,
                            onRetry = {},
                        )
                    }
                }
            }

            waitForIdle()

            onNodeWithText(
                "제품 사용을 즉시 중지하세요."
            )
                .performScrollTo()
                .assertIsDisplayed()

            onNodeWithText(
                "주의해주세요"
            )
                .performScrollTo()
                .assertIsDisplayed()

            onNodeWithText(
                "공식 근거"
            )
                .assertDoesNotExistCompat()

            onNodeWithText(
                "1. 지금 해야 할 행동"
            )
                .assertDoesNotExistCompat()

            onNodeWithText(
                "위험·상담 필수·근거 없음 상태에서는 해결됨 또는 문의 종료 버튼을 표시하지 않습니다."
            )
                .assertDoesNotExistCompat()

            onNodeWithTag(
                "resolvedAction"
            )
                .assertDoesNotExistCompat()
        }
    @Test
    @OptIn(ExperimentalTestApi::class)
    fun completionPending_resolutionActions_areVisibleAndClickable() =
        runManualComposeUiTest {
            var resolvedClicked = false
            var unresolvedClicked = false

            setContent {
                WaterCareTheme {
                    CustomerResolutionSection(
                        statusCode =
                            "COMPLETION_PENDING",
                        stateVersion = 9,
                        allowedActions =
                            listOf(
                                AllowedAction(
                                    code =
                                        InquiryActionLabels
                                            .SUBMIT_RESOLUTION_FEEDBACK
                                ),
                                AllowedAction(
                                    code =
                                        InquiryActionLabels
                                            .CUSTOMER_REPORTED_UNRESOLVED
                                ),
                            ),
                        state =
                            CustomerResolutionUiState.Idle,
                        onResolved = {
                            resolvedClicked = true
                        },
                        onUnresolved = {
                            unresolvedClicked = true
                        },
                        onRetry = {},
                        onDone = {},
                    )
                }
            }

            waitForIdle()

            onNodeWithTag(
                "submitResolutionFeedback"
            )
                .assertIsDisplayed()
                .performClick()

            assertTrue(
                "resolved action must be clickable",
                resolvedClicked,
            )

            onNodeWithTag(
                "reportUnresolved"
            )
                .assertIsDisplayed()
                .performClick()

            assertTrue(
                "unresolved action must be clickable",
                unresolvedClicked,
            )
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun cancelInquiryAction_isVisibleAndClickable() =
        runManualComposeUiTest {
            var clicked = false

            setContent {
                WaterCareTheme {
                    WorkflowActionButton(
                        action = AllowedAction(
                            code =
                                InquiryActionLabels
                                    .CANCEL_INQUIRY,
                            label = "문의 취소",
                            requiresConfirmation = true,
                        ),
                        onClick = { clicked = true },
                    )
                }
            }

            waitForIdle()

            onNodeWithTag("cancelInquiry")
                .assertIsDisplayed()
                .performClick()

            assertTrue(
                "CANCEL_INQUIRY가 허용되면 취소 버튼이 동작해야 합니다.",
                clicked,
            )
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun unsupportedWorkflowAction_isNotRendered() =
        runManualComposeUiTest {
            setContent {
                WaterCareTheme {
                    WorkflowActionButton(
                        action = AllowedAction(
                            code = "INTERNAL_ONLY_ACTION",
                        ),
                        onClick = {},
                    )
                }
            }

            waitForIdle()

            val unsupportedDoesNotExist = runCatching {
                onNodeWithText("INTERNAL_ONLY_ACTION")
                    .fetchSemanticsNode()
            }.isFailure

            assertTrue(
                "지원하지 않는 Workflow Action은 UI에 노출되면 안 됩니다.",
                unsupportedDoesNotExist,
            )
        }

    @Test
    @OptIn(ExperimentalTestApi::class)
    fun conflict_showsOnlySupportedSubmitRetryAction() = runManualComposeUiTest {
        var retried = false

        setContent {
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

        waitForIdle()

        onNodeWithTag("retrySubmitAfterConflict")
            .performScrollTo()
            .assertIsDisplayed()
            .performClick()

        val unsupportedActionDoesNotExist = runCatching {
            onNodeWithText("INTERNAL_ONLY_ACTION")
                .fetchSemanticsNode()
        }.isFailure

        assertTrue(
            "지원하지 않는 Backend Action은 고객 화면에 표시되면 안 됩니다.",
            unsupportedActionDoesNotExist,
        )

        onNodeWithTag("submitIntake")
            .performScrollTo()
            .assertIsNotEnabled()

        assertTrue(
            "SUBMIT_SYMPTOM이 허용된 충돌에서는 명시적 재시도만 실행되어야 합니다.",
            retried,
        )
    }

    private fun sampleHomeState(
        activeInquiry: ActiveInquirySummary? = ActiveInquirySummary(
            inquiryId = TEST_INQUIRY_ID,
            inquiryCode = "DEMO-INQ-002",
            statusCode = "AI_GUIDANCE",
            statusLabel = "AI 안내 확인",
        ),
    ) = CustomerHomeUiState(
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
            activeInquiry = activeInquiry,
        ),
        backendAvailable = false,
        offlinePreview = true,
        customerCareMode = CustomerCareMode.FAKE,
        dataSourceLabel = "Demo Mock 모드 · 홈·문의·안내 합성 데이터",
        intakeAvailable = true,
    )

    private fun dangerGuidance() = GuidanceDisplayModel(
        inquiryId = TEST_INQUIRY_ID,
        inquiryCode = "DEMO-DANGER-001",
        statusCode = "AI_GUIDANCE",
        stateVersion = 3,
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
        allowedActions = listOf(AllowedAction(code = InquiryActionLabels.REQUEST_CONSULTATION, label = "상담 요청")),
    )

    companion object {
        private const val TEST_SUBSCRIPTION_ID =
            "00000000-0000-4000-8000-000000000101"
        private const val TEST_INQUIRY_ID =
            "00000000-0000-4000-8000-000000000301"
    }
}
