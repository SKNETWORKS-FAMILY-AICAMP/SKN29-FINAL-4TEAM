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
import com.skn29.watercare.core.model.SymptomTopic
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
    onStartIntakePreset: (
        subscriptionId: String,
        topic: SymptomTopic,
        rawText: String,
    ) -> Unit = { subscriptionId, _, _ ->
        onStartIntake(subscriptionId)
    },
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


    LaunchedEffect(
        state.errorHttpStatus,
        state.errorCode,
        state.loggingOut,
        offlinePreview,
    ) {
        val sessionExpired =
            !offlinePreview &&
                (
                    state.errorHttpStatus == 401 ||
                        state.errorCode ==
                            "AUTHENTICATION_REQUIRED"
                )

        if (
            sessionExpired &&
            !state.loggingOut
        ) {
            viewModel.logout(onLogout)
        }
    }
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
        onStartIntakePreset =
            onStartIntakePreset,
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
        showDeveloperTools = false,
    )
}

@Composable
fun CustomerHomeContent(
    state: CustomerHomeUiState,
    displayModelCode: String? = null,
    onStartIntake: (subscriptionId: String) -> Unit,
    onStartIntakePreset: (
        subscriptionId: String,
        topic: SymptomTopic,
        rawText: String,
    ) -> Unit = { subscriptionId, _, _ ->
        onStartIntake(subscriptionId)
    },
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
        val initialLoading =
            state.loading &&
                state.home == null

        val emptySubscription =
            !state.loading &&
                state.home == null &&
                state.errorCode ==
                    "SUBSCRIPTION_EMPTY"

        val blockingError =
            !state.loading &&
                state.home == null &&
                state.error != null &&
                !emptySubscription

        val missingHome =
            !state.loading &&
                state.home == null &&
                state.error == null &&
                !emptySubscription

        if (initialLoading) {
            LoadingBlock(
                "정수기 정보를 불러오고 있어요"
            )
        }

        if (emptySubscription) {
            Column(
                modifier =
                    Modifier.fillMaxWidth(),
                verticalArrangement =
                    Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = "등록된 정수기가 없어요",
                    style =
                        MaterialTheme
                            .typography
                            .titleLarge,
                    fontWeight =
                        FontWeight.SemiBold,
                )

                Text(
                    text =
                        "구독 중인 정수기가 연결되면 홈에서 정수기 관리와 문의 기능을 이용할 수 있어요.",
                    style =
                        MaterialTheme
                            .typography
                            .bodyMedium,
                    color = palette.textMuted,
                )

                ReferenceGlassButton(
                    text = "다시 확인",
                    palette = palette,
                    onClick = onRetry,
                    enabled =
                        !state.loggingOut,
                    modifier =
                        Modifier.fillMaxWidth(),
                )

                ReferenceGlassButton(
                    text = "로그아웃",
                    palette = palette,
                    onClick = onLogout,
                    enabled =
                        !state.loggingOut,
                    modifier =
                        Modifier.fillMaxWidth(),
                )
            }
        }

        if (blockingError) {
            ErrorCard(
                message =
                    customerHomeErrorMessage(
                        requireNotNull(
                            state.error
                        )
                    ),
                onRetry = onRetry,
            )
        }

        if (missingHome) {
            Column(
                modifier =
                    Modifier.fillMaxWidth(),
                verticalArrangement =
                    Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = "정수기 정보를 확인할 수 없어요",
                    style =
                        MaterialTheme
                            .typography
                            .titleLarge,
                    fontWeight =
                        FontWeight.SemiBold,
                )

                Text(
                    text = "잠시 후 다시 확인해 주세요.",
                    style =
                        MaterialTheme
                            .typography
                            .bodyMedium,
                    color = palette.textMuted,
                )

                ReferenceGlassButton(
                    text = "다시 확인",
                    palette = palette,
                    onClick = onRetry,
                    enabled =
                        !state.loggingOut,
                    modifier =
                        Modifier.fillMaxWidth(),
                )
            }
        }

        if (
            state.loading &&
            state.home != null
        ) {
            LoadingBlock(
                "최신 정수기 정보를 확인하고 있어요"
            )
        }

        if (
            state.selectingSubscription &&
            !state.loading &&
            state.home != null
        ) {
            LoadingBlock(
                "선택한 정수기를 불러오고 있어요"
            )
        }

        if (
            state.home != null &&
            state.error != null
        ) {
            ErrorCard(
                message =
                    customerHomeErrorMessage(
                        state.error
                    ),
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
                onStartIntake = onStartIntake,
                onStartIntakePreset =
                    onStartIntakePreset,
                onOpenInquiry = { inquiryId ->
                    onOpenGuidance(
                        inquiryId,
                        MockScenario.NORMAL,
                    )
                },
                onOpenCare = onOpenCare,
            )

            FinalCustomerCareOverviewCard(
                home = home,
                activeInquiryStatusCode =
                    if (previewMode) null
                    else activeInquiryStatusCode,
                previewMode = previewMode,
                onOpenCare = onOpenCare,
            )

            FinalCustomerCareHelpBanner(
                onOpenCare = onOpenCare,
            )

            if (
                state.backendAvailable != true ||
                state.offlinePreview
            ) {
                CustomerServiceConnectionBanner(
                    backendAvailable =
                        state.backendAvailable,
                    offlinePreview =
                        state.offlinePreview,
                    hasActiveInquiry =
                        !activeInquiryId.isNullOrBlank(),
                    intakeAvailable =
                        !previewMode &&
                            state.intakeAvailable,
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