package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceGlassPanel
import com.skn29.watercare.customer.BuildConfig
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import kotlinx.coroutines.delay

@Composable
fun CustomerHomeScreen(
    offlinePreview: Boolean,
    onStartIntake: (subscriptionId: String) -> Unit,
    onOpenFollowUp: (inquiryId: String, scenario: MockScenario) -> Unit,
    onOpenGuidance: (inquiryId: String, scenario: MockScenario) -> Unit,
    onOpenCare: () -> Unit,
    onLogout: () -> Unit,
) {
    val careRepository = if (offlinePreview) {
        FakeCustomerCareRepository(
            fixtureSubscriptionId =
                WaterCareCore.customerCareRuntimeConfig.fixtureSubscriptionId,
        )
    } else {
        WaterCareCore.customerCareRepository
    }

    val viewModel: CustomerHomeViewModel = viewModel(
        factory = VmFactory { _ ->
            CustomerHomeViewModel(
                authRepository = WaterCareCore.authRepository,
                careRepository = careRepository,
                subscriptionRepository = WaterCareCore.subscriptionRepository,
                customerInquiryRepository = WaterCareCore.customerInquiryRepository,
                backendStatusRepository = WaterCareCore.backendStatusRepository,
                runtimeConfig = WaterCareCore.customerCareRuntimeConfig,
                offlinePreview = offlinePreview,
            )
        }
    )

    val state by viewModel.state.collectAsStateWithLifecycle()
    var selectionConfirmed by rememberSaveable(state.user?.id, offlinePreview) {
        mutableStateOf(false)
    }
    var pendingSubscriptionId by rememberSaveable(state.user?.id, offlinePreview) {
        mutableStateOf<String?>(null)
    }
    var displayModelCode by rememberSaveable(state.user?.id, offlinePreview) {
        mutableStateOf<String?>(null)
    }

    LaunchedEffect(
        pendingSubscriptionId,
        state.selectedSubscriptionId,
        state.selectingSubscription,
        state.error,
    ) {
        val pendingId = pendingSubscriptionId ?: return@LaunchedEffect
        when {
            !state.selectingSubscription &&
                state.selectedSubscriptionId == pendingId -> {
                selectionConfirmed = true
                pendingSubscriptionId = null
            }

            !state.selectingSubscription && state.error != null -> {
                pendingSubscriptionId = null
            }
        }
    }

    val selectableSubscriptionCount = state.subscriptions.size
    val shouldShowSubscriptionSelection =
        !offlinePreview &&
            state.customerCareMode == CustomerCareMode.REMOTE &&
            selectableSubscriptionCount > 0 &&
            !selectionConfirmed

    if (shouldShowSubscriptionSelection) {
        SubscriptionSelectionScreen(
            state = state,
            initialModelCode = displayModelCode,
            onConfirm = { selection ->
                displayModelCode = selection.modelCode
                val subscriptionId =
                    selection.subscriptionId

                when {
                    subscriptionId == null -> {
                        pendingSubscriptionId = null
                        selectionConfirmed = true
                    }

                    subscriptionId ==
                        state.selectedSubscriptionId -> {
                        selectionConfirmed = true
                    }

                    else -> {
                        pendingSubscriptionId =
                            subscriptionId
                        viewModel.selectSubscription(
                            subscriptionId
                        )
                    }
                }
            },
            onRetry = viewModel::load,
            onLogout = {
                viewModel.logout(onLogout)
            },
        )
        return
    }

    CustomerHomeContent(
        state = state,
        displayModelCode = displayModelCode,
        onStartIntake = onStartIntake,
        onOpenGuidance = { inquiryId, scenario ->
            val useRemoteFollowUpResolver =
                !offlinePreview &&
                    WaterCareCore.customerCareRuntimeConfig.mode ==
                        CustomerCareMode.REMOTE

            val activeStatus =
                state.activeInquiry
                    ?.takeIf {
                        it.inquiryId == inquiryId
                    }
                    ?.statusCode
                    ?.trim()
                    ?.uppercase()
                    .orEmpty()

            val requiresQuestionnaire =
                activeStatus.isBlank() ||
                    activeStatus == "DRAFT" ||
                    activeStatus ==
                        "QUESTIONNAIRE_IN_PROGRESS"

            if (
                useRemoteFollowUpResolver &&
                requiresQuestionnaire
            ) {
                onOpenFollowUp(
                    inquiryId,
                    scenario,
                )
            } else {
                onOpenGuidance(
                    inquiryId,
                    scenario,
                )
            }
        },
        onRetry = viewModel::load,
        onOpenCare = onOpenCare,
        onChangeProduct = {
            selectionConfirmed = false
        },
        onSelectSubscription = viewModel::selectSubscription,
        onLogout = {
            viewModel.logout(onLogout)
        },
        showDeveloperTools = BuildConfig.SHOW_DEVELOPER_TOOLS,
    )
}

@Composable
fun CustomerHomeContent(
    state: CustomerHomeUiState,
    displayModelCode: String? = null,
    onStartIntake: (subscriptionId: String) -> Unit,
    onOpenGuidance: (inquiryId: String, scenario: MockScenario) -> Unit,
    onRetry: () -> Unit,
    onLogout: () -> Unit,
    onOpenCare: () -> Unit = {},
    onChangeProduct: () -> Unit = {},
    onSelectSubscription: (String) -> Unit = {},
    showDeveloperTools: Boolean = false,
) {
    val palette = CustomerReferencePalette

    CustomerCleanScaffold(
        displayName = state.user?.displayName,
        showBottomBar = true,
        careEnabled = !state.offlinePreview,
        onOpenCare = onOpenCare,
    ) {
        if (state.loading) {
            LoadingBlock("정수기 정보를 불러오고 있어요")
        }

        state.error?.let { message ->
            ErrorCard(
                message = customerHomeErrorMessage(message),
                onRetry = onRetry,
            )
        }

        state.home?.let { home ->
            val displayModel =
                customerModelVisualSpec(
                    modelCode =
                        displayModelCode
                            ?: home.product.modelCode,
                    fallbackModelName =
                        home.product.modelName,
                )
            val previewMode =
                !displayModel.modelCode.equals(
                    home.product.modelCode,
                    ignoreCase = true,
                )

            val remoteInquiryForSelectedProduct =
                state.activeInquiry?.takeIf {
                    it.subscriptionId == home.subscriptionId
                }
            val activeInquiryId =
                remoteInquiryForSelectedProduct?.inquiryId
                    ?: home.activeInquiry?.inquiryId
            val activeInquiryStatusCode =
                remoteInquiryForSelectedProduct?.statusCode
                    ?: home.activeInquiry?.statusCode

            CustomerVisualProductHero(
                home = home,
                displayModel = displayModel,
                previewMode = previewMode,
                canChangeProduct = true,
                onChangeProduct = onChangeProduct,
            )

            CustomerServiceConnectionBanner(
                backendAvailable = state.backendAvailable,
                offlinePreview = state.offlinePreview,
                hasActiveInquiry = !activeInquiryId.isNullOrBlank(),
                intakeAvailable = !previewMode && state.intakeAvailable,
            )

            var showTodayAction by remember(
                home.subscriptionId,
                activeInquiryStatusCode,
                previewMode,
            ) {
                mutableStateOf(false)
            }
            var showQuickStatus by remember(
                home.subscriptionId,
                activeInquiryStatusCode,
                previewMode,
            ) {
                mutableStateOf(false)
            }

            LaunchedEffect(
                home.subscriptionId,
                activeInquiryStatusCode,
                previewMode,
            ) {
                showTodayAction = false
                showQuickStatus = false

                delay(120)
                showTodayAction = true

                delay(120)
                showQuickStatus = true
            }

            AnimatedVisibility(
                visible = showTodayAction,
                enter =
                    fadeIn(
                        animationSpec = tween(
                            durationMillis = 320,
                        )
                    ) +
                        slideInVertically(
                            animationSpec = tween(
                                durationMillis = 360,
                            ),
                            initialOffsetY = {
                                (it * 0.88f).toInt()
                            },
                        ) +
                        scaleIn(
                            initialScale = 0.76f,
                            animationSpec = tween(
                                durationMillis = 520,
                            ),
                        ),
            ) {
                CustomerVisualInquiryAction(
                    home = home,
                    activeInquiryId =
                        if (previewMode) null
                        else activeInquiryId,
                    activeInquiryStatusCode =
                        if (previewMode) null
                        else activeInquiryStatusCode,
                    intakeAvailable =
                        !previewMode &&
                            state.intakeAvailable,
                    intakeUnavailableReason =
                        if (previewMode) {
                            "미연결 모델 미리보기예요. 실제 문의는 구독 중인 제품을 선택하면 이용할 수 있어요."
                        } else {
                            state.intakeUnavailableReason
                        },
                    previewMode = previewMode,
                    onStartIntake = onStartIntake,
                    onOpenInquiry = { inquiryId ->
                        onOpenGuidance(
                            inquiryId,
                            MockScenario.NORMAL,
                        )
                    },
                )
            }
            AnimatedVisibility(
                visible = showQuickStatus,
                enter =
                    fadeIn(
                        animationSpec = tween(
                            durationMillis = 300,
                        )
                    ) +
                        slideInVertically(
                            animationSpec = tween(
                                durationMillis = 360,
                            ),
                            initialOffsetY = {
                                it / 6
                            },
                        ),
            ) {
                CustomerQuickStatusRow(
                    home = home,
                    previewMode = previewMode,
                    onOpenCare = onOpenCare,
                )
            }

            val fixtureGuidanceAvailable =
                state.offlinePreview ||
                    state.customerCareMode == CustomerCareMode.FAKE

            if (
                showDeveloperTools &&
                fixtureGuidanceAvailable
            ) {
                ReferenceGlassPanel(
                    palette = palette,
                ) {
                    Text(
                        "개발 검증 도구",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Black,
                    )

                    Column(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        MockScenario.entries.forEach { scenario ->
                            ReferenceGlassButton(
                                text = scenarioLabel(scenario),
                                palette = palette,
                                onClick = {
                                    onOpenGuidance(
                                        home.activeInquiry?.inquiryId
                                            ?: home.subscriptionId,
                                        scenario,
                                    )
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag(
                                        "scenario_${scenario.name}"
                                    ),
                            )
                        }
                    }
                }
            }

            ReferenceGlassButton(
                text = "로그아웃",
                palette = palette,
                onClick = onLogout,
                enabled = !state.loggingOut,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

private fun customerHomeErrorMessage(
    message: String,
): String = when {
    message.contains("Backend", ignoreCase = true) ||
        message.contains("API", ignoreCase = true) ||
        message.contains("Remote", ignoreCase = true) ->
        "정수기 정보를 가져오지 못했어요. 잠시 후 다시 확인해주세요."

    else -> "정수기 정보를 불러오는 중 문제가 생겼어요. 잠시 후 다시 시도해주세요."
}

private fun scenarioLabel(
    scenario: MockScenario,
): String = when (scenario) {
    MockScenario.NORMAL -> "일반 안내"
    MockScenario.CAUTION -> "주의 안내"
    MockScenario.DANGER -> "위험 누수"
    MockScenario.NO_EVIDENCE -> "근거 없음"
    MockScenario.BACKEND_PROCESSING -> "처리 중"
    MockScenario.AI_FAILURE -> "AI 실패"
    MockScenario.NETWORK_FAILURE -> "네트워크 실패"
}