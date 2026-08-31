@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.customer.feature.customer.guidance

import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.Lifecycle
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.scaleIn
import androidx.compose.animation.fadeIn
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.RepeatMode
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.GuidanceDisplayModel
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.RiskLevel
import com.skn29.watercare.core.model.UsageGuidanceStatus
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPanel
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.BulletList
import com.skn29.watercare.customer.feature.shared.EvidenceCard
import com.skn29.watercare.customer.feature.shared.CustomerErrorState
import com.skn29.watercare.customer.feature.shared.CustomerInitialLoadingState
import com.skn29.watercare.customer.feature.shared.CustomerSubmittingState
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.StatusBadge
import com.skn29.watercare.customer.feature.shared.WaterCareScreen
import com.skn29.watercare.customer.feature.shared.WorkflowActionButton
import kotlinx.coroutines.delay

@Composable
fun GuidanceScreen(
    inquiryId: String,
    scenario: MockScenario,
    submittedInquiryCode: String = "",
    submittedStatusCode: String? = null,
    submittedStateVersion: Int? = null,
    submittedAllowedActions: List<AllowedAction> = emptyList(),
    submittedIdempotentReplay: Boolean? = null,
    fixturePreview: Boolean = false,
    onBack: () -> Unit,
    onAuthExpired: () -> Unit = {},
    onDone: () -> Unit,
) {
    val guidanceRepository = if (fixturePreview) {
        FakeCustomerCareRepository(
            fixtureSubscriptionId =
                WaterCareCore.customerCareRuntimeConfig.fixtureSubscriptionId,
        )
    } else {
        WaterCareCore.customerCareRepository
    }

    val viewModel: GuidanceViewModel = viewModel(
        factory = VmFactory { _ ->
            GuidanceViewModel(
                inquiryId = inquiryId,
                scenario = scenario,
                repository = guidanceRepository,
                inquiryRepository = WaterCareCore.inquiryRepository,
                customerInquiryRepository =
                    WaterCareCore.customerInquiryRepository,
                followUpEnabled = false,
            )
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()
    val workflowSnapshot by
        viewModel.workflowSnapshot
            .collectAsStateWithLifecycle()
    val authExpired by
        viewModel.authExpired.collectAsStateWithLifecycle()

    LaunchedEffect(authExpired) {
        if (authExpired) {
            viewModel.consumeAuthExpired()
            onAuthExpired()
        }
    }
    val cancelState by
        viewModel.cancelState.collectAsStateWithLifecycle()

    val consultationState by
        viewModel.consultationState.collectAsStateWithLifecycle()


    // 다른 화면에서 돌아왔을 때 inquiry snapshot을 다시 확인한다.
    // refreshSilently()는 기존 안내를 지우지 않고
    // Backend workflow 변경만 반영하기 위한 새로고침이다.
    var hasResumedOnce by
        remember(
            inquiryId,
            fixturePreview,
        ) {
            mutableStateOf(false)
        }

    LifecycleEventEffect(
        Lifecycle.Event.ON_RESUME
    ) {
        if (
            hasResumedOnce &&
            !fixturePreview
        ) {
            viewModel.refreshSilently()
        } else {
            hasResumedOnce = true
        }
    }

    LaunchedEffect(cancelState) {
        if (
            cancelState is
                CancelInquiryUiState.Success &&
            !fixturePreview
        ) {
            viewModel.refreshSilently()
        }
    }

    val resolutionViewModel:
        CustomerResolutionViewModel =
        viewModel(
            factory = VmFactory { _ ->
                CustomerResolutionViewModel(
                    inquiryId = inquiryId,
                    repository =
                        WaterCareCore
                            .customerInquiryRepository,
                )
            }
        )
    val resolutionState by
        resolutionViewModel.state
            .collectAsStateWithLifecycle()
    val resolutionWorkflowSnapshot by
        resolutionViewModel.workflowSnapshot
            .collectAsStateWithLifecycle()
    val resolutionAuthExpired by
        resolutionViewModel.authExpired
            .collectAsStateWithLifecycle()

    LaunchedEffect(resolutionAuthExpired) {
        if (resolutionAuthExpired) {
            resolutionViewModel
                .consumeAuthExpired()
            onAuthExpired()
        }
    }
    var showCancelDialog by remember { mutableStateOf(false) }
    val actualInquiryCode = submittedInquiryCode.trim()
    val preferredGuidance = when (val current = state) {
        is GuidanceUiState.Content -> current.guidance
        is GuidanceUiState.NoEvidence -> current.guidance
        else -> null
    }
    val hasSubmittedWorkflowSnapshot =
        submittedStatusCode != null &&
            submittedStateVersion != null

    val liveWorkflowSnapshot =
        listOfNotNull(
            workflowSnapshot,
            resolutionWorkflowSnapshot,
        ).maxByOrNull { it.stateVersion }

    val effectiveStateVersion =
        liveWorkflowSnapshot?.stateVersion
            ?: if (hasSubmittedWorkflowSnapshot) {
                submittedStateVersion
            } else {
                preferredGuidance?.stateVersion
            }

    val effectiveAllowedActions =
        liveWorkflowSnapshot?.allowedActions
            ?: if (hasSubmittedWorkflowSnapshot) {
                submittedAllowedActions
            } else {
                preferredGuidance
                    ?.allowedActions
                    .orEmpty()
            }

    val effectiveStatusCode =
        liveWorkflowSnapshot?.statusCode
            ?: if (hasSubmittedWorkflowSnapshot) {
                submittedStatusCode
            } else {
                preferredGuidance?.statusCode
            }

    val awaitingGuidance =
        !fixturePreview &&
            state is GuidanceUiState.NotReady &&
            effectiveStatusCode
                ?.trim()
                ?.uppercase() in
            setOf(
                "AI_GUIDANCE",
                "CONSULTATION_REQUIRED",
            )

    LaunchedEffect(
        inquiryId,
        awaitingGuidance,
    ) {
        if (!awaitingGuidance) {
            return@LaunchedEffect
        }

        repeat(12) {
            delay(2_500)

            if (
                viewModel.state.value !is
                GuidanceUiState.NotReady
            ) {
                return@LaunchedEffect
            }

            viewModel.refreshSilently()
        }
    }

    val consultationResult =
        (
            state as?
                GuidanceUiState.ConsultationResult
        )?.result

    val showResolutionFirst =
        effectiveStatusCode
            ?.trim()
            ?.uppercase() ==
            "COMPLETION_PENDING"

    val progressStatusCode =
        effectiveStatusCode
            ?: when (state) {
                GuidanceUiState.Loading,
                is GuidanceUiState.NotReady ->
                    "AI_GUIDANCE"

                else ->
                    preferredGuidance?.statusCode
            }

    PullToRefreshBox(
        isRefreshing =
            state is GuidanceUiState.Loading,
        onRefresh = {
            if (!fixturePreview) {
                viewModel.load()
            }
        },
    ) {
        WaterCareScreen(title = "맞춤 해결 안내", onBack = onBack) {
            if (showResolutionFirst) {
                CustomerResolutionSection(
                    statusCode = effectiveStatusCode,
                    stateVersion = effectiveStateVersion,
                    allowedActions = effectiveAllowedActions,
                    consultationResult = consultationResult,
                    state = resolutionState,
                    onResolved =
                        resolutionViewModel::markResolved,
                    onUnresolved =
                        resolutionViewModel::reportUnresolved,
                    onRetry =
                        resolutionViewModel::retryLastAction,
                    onDone = onDone,
                )
            }

            CustomerProgressOverview(
                statusCode = progressStatusCode,
            )
            if (fixturePreview) {
                SectionCard("미리보기 화면") {
                    Text(
                        "이 화면은 기능을 둘러보기 위한 예시 화면이에요."
                    )
                }
            }


            val cancelAction = effectiveAllowedActions.firstOrNull {
                it.normalizedCode ==
                    InquiryActionLabels.CANCEL_INQUIRY
            }

            if (
                cancelAction != null &&
                cancelState !is CancelInquiryUiState.Success
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(
                        onClick = { showCancelDialog = true },
                        enabled =
                            effectiveStateVersion != null &&
                                cancelState !is
                                    CancelInquiryUiState.Cancelling,
                        modifier = Modifier.testTag(
                            "cancelInquiryAction"
                        ),
                    ) {
                        Text(
                            text = "문의 취소하기",
                            style = MaterialTheme.typography.bodySmall,
                            color =
                                MaterialTheme.colorScheme
                                    .onSurfaceVariant,
                        )
                    }
                }
            }

            when (val currentCancel = cancelState) {
                CancelInquiryUiState.Idle -> Unit

                CancelInquiryUiState.Cancelling ->
                    CustomerSubmittingState(
                        message =
                            "문의 취소를 처리하고 있어요.",
                    )

                is CancelInquiryUiState.Success ->
                    SectionCard("문의 취소 완료") {
                        LiquidGlassPill("취소됨")
                        Text(
                            "문의가 취소됐어요.",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        if (currentCancel.idempotentReplay) {
                            Text(
                                "문의 취소가 이미 처리되어 있어요.",
                                style =
                                    MaterialTheme.typography.bodySmall,
                            )
                        }
                        LiquidGlassButton(
                            text = "홈으로",
                            onClick = onDone,
                            accent = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }

                is CancelInquiryUiState.Conflict ->
                    SectionCard("문의 내용이 변경됐어요") {
                        Text("문의 내용이 변경됐어요. 최신 상태를 확인해주세요.")
                        currentCancel.currentStatus?.let { status ->
                            Text(
                                customerInquiryStatusText(status),
                                color = MaterialTheme.colorScheme.primary,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                        if (currentCancel.canRetry) {
                            LiquidGlassButton(
                                text = "문의 취소 다시 시도",
                                onClick =
                                    viewModel::retryCancelAfterConflict,
                                accent = false,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag(
                                        "retryCancelAfterConflict"
                                    ),
                            )
                        } else {
                            Text(
                                "지금은 문의를 취소할 수 없어요.",
                                style =
                                    MaterialTheme.typography.bodySmall,
                            )
                        }
                    }

                is CancelInquiryUiState.Error ->
                    ErrorCard(
                        "문의 취소를 처리하지 못했어요. 잠시 후 다시 시도해주세요.",
                        if (currentCancel.retryable) {
                            {
                                viewModel.cancelInquiry(
                                    stateVersion =
                                        effectiveStateVersion,
                                )
                            }
                        } else {
                            null
                        },
                    )
            }

            when (val current = state) {
                GuidanceUiState.Loading ->
                    CustomerInitialLoadingState(
                        title =
                            "맞춤 안내를 확인하고 있어요",
                        message =
                            "문의 상태와 해결 안내를 불러오고 있어요.",
                    )

                is GuidanceUiState.Content ->
                    GuidanceResultReveal {
                        GuidanceContent(
                            guidance =
                                current.guidance
                                    .withInquiryCode(
                                        actualInquiryCode
                                    ),
                            noEvidence = false,
                            onRetry = viewModel::load,
                        )
                    }

                is GuidanceUiState.ConsultationResult ->
                    Unit

                is GuidanceUiState.ConsultationResultNotReady ->
                    CustomerErrorState(
                        title =
                            "상담 결과를 아직 확인할 수 없어요",
                        message = current.message,
                        onRetry = viewModel::load,
                    )

                is GuidanceUiState.NoEvidence ->
                    GuidanceResultReveal {
                        GuidanceContent(
                            guidance =
                                current.guidance
                                    .withInquiryCode(
                                        actualInquiryCode
                                    ),
                            noEvidence = true,
                            onRetry = viewModel::load,
                        )
                    }

                is GuidanceUiState.NotReady ->
                    CustomerInitialLoadingState(
                        title =
                            "안내를 준비하고 있어요",
                        message = current.message,
                    )

                is GuidanceUiState.AiFailure ->
                    GuidanceFailureStateContent(
                        state = current,
                        onRetry = viewModel::load,
                    )

                is GuidanceUiState.NetworkFailure ->
                    GuidanceFailureStateContent(
                        state = current,
                        onRetry = viewModel::load,
                    )

                is GuidanceUiState.Error ->
                    CustomerErrorState(
                        title =
                            "현재 안내를 확인할 수 없어요",
                        message =
                            "잠시 후 다시 확인해주세요.",
                        onRetry =
                            if (current.retryable) {
                                viewModel::load
                            } else {
                                null
                            },
                    )
            }

            val consultationAction =
                effectiveAllowedActions.firstOrNull {
                    it.normalizedCode ==
                        InquiryActionLabels.REQUEST_CONSULTATION
                }

            if (
                consultationAction != null &&
                consultationState !is
                    ConsultationRequestUiState.Success
            ) {
                SectionCard("상담 연결") {
                    WorkflowActionButton(
                        action = consultationAction,
                        enabled =
                            consultationState !is
                                ConsultationRequestUiState.Requesting,
                        onClick =
                            viewModel::requestConsultation,
                    )

                    Text(
                        "안내만으로 해결이 어렵다면 지금까지 입력한 내용을 상담사에게 그대로 전달할 수 있어요.",
                        style =
                            MaterialTheme.typography.bodySmall,
                        color =
                            MaterialTheme.colorScheme
                                .onSurfaceVariant,
                    )
                }
            }

            when (val currentConsultation = consultationState) {
                ConsultationRequestUiState.Idle -> Unit

                ConsultationRequestUiState.Requesting ->
                    CustomerSubmittingState(
                        message =
                            "상담사에게 문의 내용을 전달하고 있어요.",
                    )

                is ConsultationRequestUiState.Success ->
                    SectionCard("상담 요청 완료") {
                        LiquidGlassPill("상담 접수됨")

                        Text(
                            "상담 요청이 전달됐어요.",
                            style =
                                MaterialTheme.typography
                                    .titleMedium,
                            fontWeight = FontWeight.Bold,
                        )

                        Text(
                            customerInquiryStatusText(
                                currentConsultation
                                    .snapshot
                                    .statusCode
                            )
                        )

                        Text(
                            "지금까지 입력한 증상과 문의 내용이 상담사에게 함께 전달됐어요.",
                            style =
                                MaterialTheme.typography
                                    .bodyMedium,
                        )

                        Text(
                            "다음 진행 순서",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                        )

                        BulletList(
                            listOf(
                                "상담사가 문의 내용을 확인해요",
                                "필요한 경우 연락 또는 방문 안내를 드려요",
                                "진행 상태는 이 문의에서 계속 확인할 수 있어요",
                            )
                        )

                        if (
                            currentConsultation
                                .idempotentReplay
                        ) {
                            Text(
                                "상담 요청이 이미 처리되어 있어요.",
                                style =
                                    MaterialTheme.typography
                                        .bodySmall,
                                color =
                                    MaterialTheme.colorScheme
                                        .onSurfaceVariant,
                            )
                        }

                        LiquidGlassButton(
                            text = "홈에서 진행 상태 보기",
                            onClick = onDone,
                            accent = true,
                            modifier =
                                Modifier.fillMaxWidth(),
                        )
                    }

                is ConsultationRequestUiState.Conflict ->
                    SectionCard(
                        "문의 상태가 변경됐어요"
                    ) {
                        Text("문의 내용이 변경됐어요. 최신 상태를 확인해주세요.")

                        Text(
                            customerInquiryStatusText(
                                currentConsultation
                                    .snapshot
                                    .statusCode
                            )
                        )

                        if (
                            currentConsultation.canRetry
                        ) {
                            LiquidGlassButton(
                                text =
                                    "상담 다시 요청",
                                onClick =
                                    viewModel::
                                        retryConsultationAfterConflict,
                                accent = true,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag(
                                        "retryConsultationAfterConflict"
                                    ),
                            )
                        } else {
                            Text(
                                "지금은 상담 연결을 다시 요청할 수 없어요.",
                                style =
                                    MaterialTheme.typography
                                        .bodySmall,
                                color =
                                    MaterialTheme.colorScheme
                                        .onSurfaceVariant,
                            )
                        }
                    }

                is ConsultationRequestUiState.Error ->
                    ErrorCard(
                        "상담 요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요.",
                        if (
                            currentConsultation.retryable
                        ) {
                            viewModel::
                                retryConsultationRequest
                        } else {
                            null
                        },
                    )
            }

            if (!showResolutionFirst) {
                CustomerResolutionSection(
                    statusCode = effectiveStatusCode,
                    stateVersion = effectiveStateVersion,
                    allowedActions = effectiveAllowedActions,
                    consultationResult = consultationResult,
                    state = resolutionState,
                    onResolved =
                        resolutionViewModel::markResolved,
                    onUnresolved =
                        resolutionViewModel::reportUnresolved,
                    onRetry =
                        resolutionViewModel::retryLastAction,
                    onDone = onDone,
                )
            }

            if (showCancelDialog) {
                val action = effectiveAllowedActions.firstOrNull {
                    it.normalizedCode ==
                        InquiryActionLabels.CANCEL_INQUIRY
                }
                AlertDialog(
                    onDismissRequest = {
                        showCancelDialog = false
                    },
                    title = {
                        Text("문의를 취소할까요?")
                    },
                    text = {
                        Text(
                            action?.confirmationMessage
                                ?.takeIf(String::isNotBlank)
                                ?: "취소 후에는 현재 문의 흐름을 계속 진행할 수 없습니다."
                        )
                    },
                    confirmButton = {
                        TextButton(
                            onClick = {
                                showCancelDialog = false
                                viewModel.cancelInquiry(
                                    stateVersion =
                                        effectiveStateVersion,
                                    reasonCode =
                                        "CUSTOMER_REQUEST",
                                )
                            },
                            modifier =
                                Modifier.testTag(
                                    "confirmCancelInquiry"
                                ),
                        ) {
                            Text("문의 취소")
                        }
                    },
                    dismissButton = {
                        TextButton(
                            onClick = {
                                showCancelDialog = false
                            }
                        ) {
                            Text("돌아가기")
                        }
                    },
                )
            }
        }
    }
}

private fun GuidanceDisplayModel.withInquiryCode(
    submittedInquiryCode: String,
): GuidanceDisplayModel =
    submittedInquiryCode.takeIf(String::isNotEmpty)
        ?.let { copy(inquiryCode = it) }
        ?: this


@Composable
private fun CustomerProgressOverview(
    statusCode: String?,
) {
    LiquidGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("guidanceProgress"),
        strong = true,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            LiquidGlassPill("현재 진행 상태")

        }

        Text(
            customerInquiryProgressHeadline(statusCode),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
        )

        Text(
            customerInquiryProgressDescription(statusCode),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

    }
}

private fun customerInquiryCurrentStep(
    statusCode: String?,
): Int = when (statusCode?.trim()?.uppercase()) {
    "DRAFT" -> 1
    "QUESTIONNAIRE_IN_PROGRESS" -> 2
    "AI_GUIDANCE" -> 3
    "CONSULTATION_REQUIRED",
    "CONSULTATION_IN_PROGRESS",
    "VISIT_REVIEW_PENDING",
    "VISIT_SCHEDULING",
    "VISIT_SCHEDULED",
    "COMPLETION_PENDING",
    "REVISIT_REQUIRED",
    "REOPENED",
    "RESOLVED" -> 4
    "CANCELLED" -> 1
    else -> 1
}

private fun customerInquiryProgressHeadline(
    statusCode: String?,
): String = when (statusCode?.trim()?.uppercase()) {
    "DRAFT" ->
        "문의가 접수됐어요"

    "QUESTIONNAIRE_IN_PROGRESS" ->
        "증상을 조금 더 확인할게요"

    "AI_GUIDANCE" ->
        "해결 방법을 확인해보세요"

    "CONSULTATION_REQUIRED" ->
        "상담 연결이 필요해요"

    "CONSULTATION_IN_PROGRESS" ->
        "상담사가 문의를 확인하고 있어요"

    "VISIT_REVIEW_PENDING" ->
        "방문 점검이 필요한지 확인하고 있어요"

    "VISIT_SCHEDULING" ->
        "방문 일정을 조율하고 있어요"

    "VISIT_SCHEDULED" ->
        "방문 일정이 정해졌어요"

    "COMPLETION_PENDING" ->
        "처리 결과를 확인하고 있어요"

    "REVISIT_REQUIRED" ->
        "추가 확인이 필요해요"

    "REOPENED" ->
        "문의 내용을 다시 확인하고 있어요"

    "RESOLVED" ->
        "문의 처리가 완료됐어요"

    "CANCELLED" ->
        "문의가 취소됐어요"

    else ->
        "문의 내용을 확인하고 있어요"
}

private fun customerInquiryProgressDescription(
    statusCode: String?,
): String = when (statusCode?.trim()?.uppercase()) {
    "DRAFT" ->
        "입력한 증상 내용을 안전하게 저장했어요."

    "QUESTIONNAIRE_IN_PROGRESS" ->
        "정확한 안내를 위해 필요한 내용만 간단히 더 확인할게요."

    "AI_GUIDANCE" ->
        "확인된 정보를 바탕으로 지금 할 수 있는 방법을 안내해드려요."

    "CONSULTATION_REQUIRED" ->
        "지금까지 입력한 내용을 다시 설명하지 않아도 상담사에게 그대로 전달할 수 있어요."

    "CONSULTATION_IN_PROGRESS" ->
        "상담사가 지금까지 입력한 증상과 안내 내용을 함께 확인하고 있어요."

    "VISIT_REVIEW_PENDING",
    "VISIT_SCHEDULING",
    "VISIT_SCHEDULED" ->
        "상담 내용이 이어진 상태로 방문 점검 절차를 진행하고 있어요."

    "COMPLETION_PENDING" ->
        "마지막으로 문제가 해결됐는지 확인하고 있어요."

    "REVISIT_REQUIRED",
    "REOPENED" ->
        "기존 문의 내용을 유지한 채 필요한 부분을 다시 확인하고 있어요."

    "RESOLVED" ->
        "확인과 상담 과정이 모두 완료됐어요."

    "CANCELLED" ->
        "이 문의는 더 이상 진행되지 않아요."

    else ->
        "현재 진행 상태를 확인하고 있어요."
}

@Composable
private fun SubmissionReceiptCard(
    inquiryCode: String,
    statusCode: String?,
    stateVersion: Int?,
    allowedActions: List<AllowedAction>,
    idempotentReplay: Boolean?,
) {
    LiquidGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("submissionReceipt"),
        strong = true,
    ) {
        LiquidGlassPill("증상 접수가 완료됐어요")

        Text(
            "입력한 증상을 확인하고 있어요.",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
        )
        statusCode
            ?.trim()
            ?.uppercase()
            ?.takeIf(String::isNotEmpty)
            ?.let { code ->
                Text(
                    customerInquiryStatusText(code),
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                )
            }

        Text(
            "필요한 내용이 있으면 이 화면에서 하나씩 안내해드릴게요.",
            style = MaterialTheme.typography.bodyMedium,
        )

        if (idempotentReplay == true) {
            Text(
                "이미 접수된 내용을 다시 확인했습니다.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun customerInquiryStatusText(
    statusCode: String,
): String = when (statusCode.trim().uppercase()) {
    "DRAFT" -> "접수 내용을 확인하고 있어요"
    "QUESTIONNAIRE_IN_PROGRESS" -> "증상을 조금 더 확인하고 있어요"
    "AI_GUIDANCE" -> "문제 해결 안내를 확인해주세요"
    "CONSULTATION_REQUIRED" -> "상담이 필요해요"
    "CONSULTATION_IN_PROGRESS" -> "상담을 진행하고 있어요"
    "VISIT_REVIEW_PENDING" -> "방문 점검이 필요한지 확인하고 있어요"
    "VISIT_SCHEDULING" -> "방문 일정을 조율하고 있어요"
    "VISIT_SCHEDULED" -> "방문 일정이 잡혔어요"
    "COMPLETION_PENDING" -> "처리 결과를 확인하고 있어요"
    "REVISIT_REQUIRED" -> "추가 방문 점검이 필요해요"
    "REOPENED" -> "문의 내용을 다시 확인하고 있어요"
    "RESOLVED" -> "처리가 완료됐어요"
    "CANCELLED" -> "접수가 취소됐어요"
    else -> "접수 내용을 확인하고 있어요"
}

@Composable
private fun GuidanceResultReveal(
    content: @Composable () -> Unit,
) {
    var visible by remember {
        mutableStateOf(false)
    }

    LaunchedEffect(Unit) {
        delay(70)
        visible = true
    }

    AnimatedVisibility(
        visible = visible,
        enter =
            fadeIn(
                animationSpec = tween(
                    durationMillis = 360,
                )
            ) +
                slideInVertically(
                    animationSpec = tween(
                        durationMillis = 480,
                    ),
                    initialOffsetY = {
                        (it * 0.72f).toInt()
                    },
                ) +
                scaleIn(
                    initialScale = 0.96f,
                    animationSpec = tween(
                        durationMillis = 500,
                    ),
                ),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            content()
        }
    }
}
@Composable
@Suppress("UNUSED_PARAMETER")
fun GuidanceContent(
    guidance: GuidanceDisplayModel,
    noEvidence: Boolean,
    onRetry: () -> Unit,
) {
    val safetyCritical =
        guidance.requiresConsultation ||
            guidance.riskLevel == RiskLevel.DANGER ||
            guidance.usageStatus == UsageGuidanceStatus.TOTAL_STOP ||
            guidance.usageStatus ==
                UsageGuidanceStatus.PENDING_CONSULTATION

    val dangerous = safetyCritical || noEvidence

    val headline = when {
        noEvidence ->
            "안내를 위해 조금 더 확인이 필요해요"
        guidance.usageStatus == UsageGuidanceStatus.TOTAL_STOP ->
            "안전을 위해 사용을 멈춰주세요"
        guidance.usageStatus == UsageGuidanceStatus.PENDING_CONSULTATION ->
            "사용 전에 상담이 필요해요"
        guidance.riskLevel == RiskLevel.DANGER ->
            "안전을 먼저 확인해주세요"
        else ->
            "지금 할 수 있는 해결 방법을 확인해보세요"
    }

    val heroMessage = when {
        dangerous ->
            "안전을 위해 아래 내용을 순서대로 확인해주세요. 필요하면 바로 상담을 연결할 수 있어요."
        else ->
            "가장 먼저 확인해야 할 내용부터 순서대로 정리했어요."
    }

    LiquidGlassPanel(
        modifier = Modifier.fillMaxWidth(),
        strong = !dangerous,
        danger = dangerous,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 132.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                LiquidGlassPill(
                    if (dangerous) "안전 확인"
                    else "맞춤 안내"
                )

                StatusBadge(
                    guidance.riskLevel,
                    guidance.usageStatus,
                )

                Text(
                    text = headline,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                )

                Text(
                    text = heroMessage,
                    style = MaterialTheme.typography.bodyMedium,
                    color =
                        MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Image(
                painter = painterResource(R.drawable.mascot_customer),
                contentDescription = "맞춤 안내 캐릭터",
                modifier = Modifier.size(88.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }

    val showUsage =
        guidance.usageMessage.isNotBlank() ||
            guidance.restrictedFunctions.isNotEmpty() ||
            safetyCritical

    if (showUsage) {
        SectionCard(
            "현재 사용 상태",
            isDanger = dangerous,
        ) {
            StatusBadge(
                guidance.riskLevel,
                guidance.usageStatus,
            )

            if (guidance.usageMessage.isNotBlank()) {
                Text(
                    guidance.usageMessage,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            if (guidance.restrictedFunctions.isNotEmpty()) {
                Text(
                    "지금 사용할 수 없는 기능",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                )
                BulletList(guidance.restrictedFunctions)
            }
        }
    }

    if (
        guidance.nextAction.isNotBlank() ||
        guidance.safeActions.isNotEmpty()
    ) {
        SectionCard(
            "이 순서대로 해보세요",
            isDanger = dangerous,
        ) {
            if (guidance.nextAction.isNotBlank()) {
                Text(
                    guidance.nextAction,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
            }

            if (guidance.safeActions.isNotEmpty()) {
                GuidanceActionSteps(guidance.safeActions)
            }
        }
    }

    if (guidance.prohibitedActions.isNotEmpty()) {
        SectionCard(
            "주의해주세요",
            isDanger = dangerous,
        ) {
            BulletList(guidance.prohibitedActions)
        }
    }

    if (guidance.escalationConditions.isNotEmpty()) {
        SectionCard(
            "상담이 필요한 경우",
            isDanger = dangerous,
        ) {
            BulletList(guidance.escalationConditions)
        }
    }

    if (guidance.symptomSummary.isNotBlank()) {
        SectionCard("입력한 증상") {
            Text(
                guidance.symptomSummary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }

    if (guidance.evidence.isNotEmpty()) {
        SectionCard("안내 기준") {
            Text(
                "확인된 정보를 기준으로 안내했어요.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            guidance.evidence.forEach {
                EvidenceCard(it)
            }
        }
    }
}

@Composable
private fun GuidanceActionSteps(
    actions: List<String>,
) {
    Column(
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        actions.forEachIndexed { index, action ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(
                        MaterialTheme.colorScheme.primary.copy(alpha = 0.055f)
                    )
                    .padding(horizontal = 12.dp, vertical = 11.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    modifier = Modifier
                        .size(32.dp)
                        .clip(CircleShape)
                        .background(
                            MaterialTheme.colorScheme.primary.copy(alpha = 0.13f)
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "${index + 1}",
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                    )
                }

                Text(
                    text = action,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                    fontWeight = FontWeight.Medium,
                )
            }
        }
    }
}

@Composable
internal fun GuidanceFailureStateContent(
    state: GuidanceUiState,
    onRetry: () -> Unit,
) {
    when (state) {
        is GuidanceUiState.NotReady -> FailureFallback(
            title = "맞춤 안내 준비 중",
            message = "맞춤 안내를 준비하고 있어요. 잠시 후 다시 확인해주세요.",
            retryable = true,
            onRetry = onRetry,
        )

        is GuidanceUiState.AiFailure -> FailureFallback(
            title = "지금은 안내를 준비하지 못했어요",
            message = "지금은 맞춤 안내를 준비하지 못했어요. 잠시 후 다시 시도해주세요.",
            retryable = state.retryable,
            onRetry = onRetry,
        )

        is GuidanceUiState.NetworkFailure -> FailureFallback(
            title = "연결이 잠시 불안정해요",
            message = "서비스에 연결할 수 없어요. 잠시 후 다시 시도해주세요.",
            retryable = state.retryable,
            onRetry = onRetry,
        )

        else -> Unit
    }
}

@Composable
private fun FailureFallback(
    title: String,
    message: String,
    retryable: Boolean,
    onRetry: () -> Unit,
) {
    LiquidGlassPanel(strong = true) {
        Text(
            title,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "입력하신 문의 내용은 그대로 보관되어 있어요. 잠시 후 다시 확인해주세요."
        )
    }

    ErrorCard(
        message,
        if (retryable) onRetry else null,
    )
}
