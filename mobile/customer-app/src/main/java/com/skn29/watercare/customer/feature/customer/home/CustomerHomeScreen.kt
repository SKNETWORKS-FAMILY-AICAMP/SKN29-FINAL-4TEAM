@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.customer.feature.customer.home

import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.first
import com.skn29.watercare.customer.feature.customer.guidance.InquiryCancelRuntime
import com.skn29.watercare.customer.feature.customer.guidance.CancelInquiryUiState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.material3.TextButton
import androidx.compose.material3.AlertDialog
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
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceGlassPanel
import com.skn29.watercare.customer.BuildConfig
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.CustomerInitialLoadingState
import com.skn29.watercare.customer.feature.shared.CustomerEmptyState
import com.skn29.watercare.customer.feature.shared.CustomerErrorState
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
    onOpenGuidance: (
        inquiryId: String,
        scenario: MockScenario,
        statusCode: String?,
        stateVersion: Int?,
        allowedActions: List<AllowedAction>,
    ) -> Unit,
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

    // 화면 최초 진입은 ViewModel init에서 이미 load()를 수행한다.
    // 이후 다른 화면에서 홈으로 돌아오는 ON_RESUME에서만
    // 다시 조회해 서버 최신 상태를 반영한다.
    // 최초 진입에서도 다시 load하면 같은 API가 연속 호출될 수 있으므로
    // hasResumedOnce로 중복 조회를 막는다.
    var hasResumedOnce by
        rememberSaveable {
            mutableStateOf(false)
        }

    LifecycleEventEffect(
        Lifecycle.Event.ON_RESUME
    ) {
        if (hasResumedOnce) {
            if (
                !state.loading &&
                !state.loggingOut
            ) {
                viewModel.load()
            }
        } else {
            hasResumedOnce = true
        }
    }


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
            state.customerCareMode ==
                CustomerCareMode.REMOTE &&
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

    PullToRefreshBox(
        isRefreshing =
            state.loading &&
                state.home != null,
        onRefresh = {
            if (
                !state.loading &&
                !state.loggingOut
            ) {
                viewModel.load()
            }
        },
    ) {
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

                val activeSnapshot =
                    state.activeInquiry
                        ?.takeIf {
                            it.inquiryId == inquiryId
                        }

                val activeStatus =
                    activeSnapshot
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
                        activeSnapshot?.statusCode,
                        activeSnapshot?.stateVersion,
                        activeSnapshot
                            ?.allowedActions
                            .orEmpty(),
                    )
                }
            },
            onContinueQuestionnaire = { inquiryId ->
                onOpenFollowUp(
                    inquiryId,
                    MockScenario.NORMAL,
                )
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
    onContinueQuestionnaire: (inquiryId: String) -> Unit = {},
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
            // 최초 홈 데이터가 아직 없을 때는 빈 화면 대신
            // 명시적인 로딩 상태를 보여준다.
            CustomerInitialLoadingState(
                message =
                    "정수기와 문의 상태를 확인하고 있어요.",
            )
        }

        if (emptySubscription) {
            // Empty는 장애가 아니라
            // 정상 응답이지만 구독 정수기가 없는 상태이다.
            // Error 표현을 쓰지 않고 다음에 할 수 있는 행동을 안내한다.
            CustomerEmptyState(
                title =
                    "등록된 정수기가 없어요",
                message =
                    "구독 중인 정수기가 연결되면 홈에서 정수기 관리와 문의 기능을 이용할 수 있어요.",
                actionLabel =
                    "다시 확인",
                onAction = onRetry,
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

        if (blockingError) {
            // 초기 조회 실패는 보여줄 기존 데이터가 없으므로
            // 전체 상태를 Error UI로 명확히 안내한다.
            CustomerErrorState(
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
            // error message도 없고 home data도 없는 비정상 상태.
            // 빈 화면을 남기지 않고 사용자가 복구할 수 있게 한다.
            CustomerErrorState(
                title =
                    "정수기 정보를 확인할 수 없어요",
                message =
                    "잠시 후 다시 확인해 주세요.",
                retryLabel =
                    "다시 확인",
                onRetry = onRetry,
            )
        }

        if (
            state.loading &&
            state.home != null
        ) {
            // 기존 홈 데이터가 있는 새로고침은 화면을
            // 로딩 화면으로 덮지 않는다.
            // PullToRefreshBox의 indicator만 보여
            // 사용자가 보던 정보를 유지한다.
        }

        if (
            state.selectingSubscription &&
            !state.loading &&
            state.home != null
        ) {
            // 제품 변경 중에도 기존 홈을 유지한다.
            // 선택 결과가 도착한 뒤 화면 데이터만 교체해
            // 깜빡임을 줄인다.
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

            val cancelScope =
                rememberCoroutineScope()

            val showCancelDialog =
                remember {
                    mutableStateOf(false)
                }

            val cancelInProgress =
                remember {
                    mutableStateOf(false)
                }

            val cancelError =
                remember {
                    mutableStateOf<String?>(
                        null
                    )
                }

            val cancelAvailable =
                !previewMode &&
                    remoteInquiryForSelectedProduct
                        ?.let { snapshot ->
                            val status =
                                snapshot.statusCode
                                    .trim()
                                    .uppercase()

                            status in setOf(
                                "DRAFT",
                                "QUESTIONNAIRE_IN_PROGRESS",
                            ) &&
                                snapshot.stateVersion >= 1 &&
                                snapshot.allowedActions.any {
                                    action ->
                                    action.normalizedCode ==
                                        InquiryActionLabels
                                            .CANCEL_INQUIRY
                                }
                        } == true

            val followUpAvailable =
                !previewMode &&
                    remoteInquiryForSelectedProduct
                        ?.let { snapshot ->
                            snapshot.statusCode
                                .trim()
                                .uppercase() ==
                                "QUESTIONNAIRE_IN_PROGRESS" &&
                                snapshot.stateVersion >= 1 &&
                                snapshot.allowedActions.any {
                                    action ->
                                    action.normalizedCode ==
                                        InquiryActionLabels
                                            .SUBMIT_ANSWERS
                                }
                        } == true

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
                activeInquiryStatusCode =
                    if (previewMode) null
                    else activeInquiryStatusCode,
                cancelAvailable =
                    cancelAvailable &&
                        !cancelInProgress.value,
                followUpAvailable =
                    followUpAvailable &&
                        !cancelInProgress.value,
                onContinueQuestionnaire = {
                    activeInquiryId
                        ?.takeIf(String::isNotBlank)
                        ?.let { inquiryId ->
                            onContinueQuestionnaire(
                                inquiryId
                            )
                        }
                },
                onCancelInquiry = {
                    if (
                        cancelAvailable &&
                        !cancelInProgress.value
                    ) {
                        showCancelDialog.value =
                            true
                    }
                },
                previewMode = previewMode,
            )

            if (
                showCancelDialog.value &&
                cancelAvailable &&
                !cancelInProgress.value
            ) {
                AlertDialog(
                    onDismissRequest = {
                        showCancelDialog.value =
                            false
                    },
                    title = {
                        Text(
                            "접수를 취소할까요?"
                        )
                    },
                    text = {
                        Text(
                            "취소 후에는 현재 문의 흐름을 계속 진행할 수 없습니다."
                        )
                    },
                    confirmButton = {
                        TextButton(
                            onClick = {
                                // 이 AlertDialog는 cancelAvailable이 true일 때만
                                // 화면에 생성된다.
                                // cancelAvailable은 active inquiry가 존재해야 true가 되므로
                                // 여기서 nullable 검사를 다시 하면 항상 true인 중복 조건이 된다.
                                // requireNotNull로 이 화면의 선행 조건을 코드에 명시한다.
                                val snapshot =
                                    requireNotNull(
                                        remoteInquiryForSelectedProduct
                                    )

                                    showCancelDialog.value =
                                        false

                                    cancelInProgress.value =
                                        true

                                    cancelError.value =
                                        null

                                    val runtime =
                                        InquiryCancelRuntime(
                                            inquiryId =
                                                snapshot
                                                    .inquiryId,
                                            repository =
                                                WaterCareCore
                                                    .inquiryRepository,
                                            scope =
                                                cancelScope,
                                            onAuthExpired = {
                                                onLogout()
                                            },
                                        )

                                    runtime.cancelInquiry(
                                        stateVersion =
                                            snapshot
                                                .stateVersion,
                                    )

                                    cancelScope.launch {
                                        val terminal =
                                            runtime.state
                                                .first {
                                                    current ->
                                                    current !=
                                                        CancelInquiryUiState.Idle &&
                                                        current !=
                                                        CancelInquiryUiState.Cancelling
                                                }

                                        cancelInProgress.value =
                                            false

                                        when (terminal) {
                                            is CancelInquiryUiState.Success -> {
                                                onRetry()
                                            }

                                            is CancelInquiryUiState.Conflict -> {
                                                cancelError.value =
                                                    terminal.message

                                                onRetry()
                                            }

                                            is CancelInquiryUiState.Error -> {
                                                cancelError.value =
                                                    terminal.message
                                            }

                                            else -> Unit
                                        }
                                    }
                            },
                            modifier =
                                Modifier.testTag(
                                    "confirmHomeCancelInquiry"
                                ),
                        ) {
                            Text(
                                "접수 취소"
                            )
                        }
                    },
                    dismissButton = {
                        TextButton(
                            onClick = {
                                showCancelDialog.value =
                                    false
                            },
                            modifier =
                                Modifier.testTag(
                                    "dismissHomeCancelInquiry"
                                ),
                        ) {
                            Text(
                                "돌아가기"
                            )
                        }
                    },
                )
            }

            cancelError.value
                ?.let { message ->
                    AlertDialog(
                        onDismissRequest = {
                            cancelError.value =
                                null
                        },
                        title = {
                            Text(
                                "접수 취소를 확인해주세요"
                            )
                        },
                        text = {
                            Text(message)
                        },
                        confirmButton = {
                            TextButton(
                                onClick = {
                                    cancelError.value =
                                        null
                                },
                            ) {
                                Text(
                                    "확인"
                                )
                            }
                        },
                    )
                }

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
