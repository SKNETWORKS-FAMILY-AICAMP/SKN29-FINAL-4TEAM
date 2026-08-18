package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
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
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.BulletList
import com.skn29.watercare.customer.feature.shared.EvidenceCard
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.StatusBadge
import com.skn29.watercare.customer.feature.shared.WaterCareScreen
import com.skn29.watercare.customer.feature.shared.WorkflowActionButton

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
    val cancelState by
        viewModel.cancelState.collectAsStateWithLifecycle()

    val consultationState by
        viewModel.consultationState.collectAsStateWithLifecycle()
    var showCancelDialog by remember { mutableStateOf(false) }
    val actualInquiryCode = submittedInquiryCode.trim()
    val preferredGuidance = when (val current = state) {
        is GuidanceUiState.Content -> current.guidance
        is GuidanceUiState.NoEvidence -> current.guidance
        else -> null
    }
    val effectiveStateVersion =
        preferredGuidance?.stateVersion
            ?: submittedStateVersion
    val effectiveAllowedActions =
        preferredGuidance?.allowedActions
            ?: submittedAllowedActions

    WaterCareScreen(title = "AI 안내", onBack = onBack) {
        CustomerProgressOverview(
            statusCode = preferredGuidance?.statusCode ?: submittedStatusCode,
        )
        if (fixturePreview) {
            SectionCard("미리보기 화면") {
                Text(
                    "이 화면은 기능을 둘러보기 위한 예시 화면이에요."
                )
            }
        }

        if (actualInquiryCode.isNotEmpty()) {
            SubmissionReceiptCard(
                inquiryCode = actualInquiryCode,
                statusCode =
                    preferredGuidance?.statusCode
                        ?: submittedStatusCode,
                stateVersion = effectiveStateVersion,
                allowedActions = effectiveAllowedActions,
                idempotentReplay = submittedIdempotentReplay,
            )
        }


        val cancelAction = effectiveAllowedActions.firstOrNull {
            it.normalizedCode ==
                InquiryActionLabels.CANCEL_INQUIRY
        }

        if (
            cancelAction != null &&
            cancelState !is CancelInquiryUiState.Success
        ) {
            SectionCard("문의 취소") {
                WorkflowActionButton(
                    action = cancelAction,
                    enabled =
                        effectiveStateVersion != null &&
                            cancelState !is
                                CancelInquiryUiState.Cancelling,
                    onClick = { showCancelDialog = true },
                )
                Text(
                    "진행 중인 문의는 상황에 따라 취소할 수 있어요.",
                    style = MaterialTheme.typography.bodySmall,
                    color =
                        MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        when (val currentCancel = cancelState) {
            CancelInquiryUiState.Idle -> Unit

            CancelInquiryUiState.Cancelling ->
                LoadingBlock("문의를 취소하는 중입니다")

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
                            "현재 상태에서는 문의를 취소할 수 없습니다.",
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
                LoadingBlock("해결 방법을 준비하고 있어요")

            is GuidanceUiState.Content -> GuidanceContent(
                guidance = current.guidance.withInquiryCode(
                    actualInquiryCode
                ),
                noEvidence = false,
                onRetry = viewModel::load,
            )

            is GuidanceUiState.NoEvidence -> GuidanceContent(
                guidance = current.guidance.withInquiryCode(
                    actualInquiryCode
                ),
                noEvidence = true,
                onRetry = viewModel::load,
            )

            is GuidanceUiState.NotReady -> FailureFallback(
                title = "AI 안내 준비 중",
                message = "AI 안내를 준비하고 있어요. 잠시 후 다시 확인해주세요.",
                retryable = true,
                onRetry = viewModel::load,
            )

            is GuidanceUiState.AiFailure -> FailureFallback(
                title = "지금은 안내를 준비하지 못했어요",
                message = "지금은 AI 안내를 준비하지 못했어요. 잠시 후 다시 시도해주세요.",
                retryable = current.retryable,
                onRetry = viewModel::load,
            )

            is GuidanceUiState.NetworkFailure -> FailureFallback(
                title = "연결이 잠시 불안정해요",
                message = "서비스에 연결할 수 없어요. 잠시 후 다시 시도해주세요.",
                retryable = current.retryable,
                onRetry = viewModel::load,
            )

            is GuidanceUiState.Error ->
                ErrorCard(
                    "현재 안내를 확인할 수 없어요. 잠시 후 다시 시도해주세요.",
                    if (current.retryable) viewModel::load else null,
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
                LoadingBlock(
                    "상담 요청을 보내는 중입니다"
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
    val currentStep = customerInquiryCurrentStep(statusCode)

    SectionCard("문의 진행 상황") {
        Text(
            customerInquiryProgressHeadline(statusCode),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.ExtraBold,
        )

        Text(
            customerInquiryProgressDescription(statusCode),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            CustomerProgressStep(
                number = 1,
                title = "문의 접수",
                description = "증상 내용을 전달했어요",
                currentStep = currentStep,
            )
            CustomerProgressStep(
                number = 2,
                title = "추가 확인",
                description = "필요한 내용을 조금 더 확인해요",
                currentStep = currentStep,
            )
            CustomerProgressStep(
                number = 3,
                title = "해결 안내",
                description = "공식 근거를 바탕으로 해결 방법을 확인해요",
                currentStep = currentStep,
            )
            CustomerProgressStep(
                number = 4,
                title = "상담 연결",
                description = "필요한 경우 상담사에게 그대로 이어져요",
                currentStep = currentStep,
            )
        }
    }
}

@Composable
private fun CustomerProgressStep(
    number: Int,
    title: String,
    description: String,
    currentStep: Int,
) {
    val completed = number < currentStep
    val current = number == currentStep

    Row(
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            when {
                completed -> "✓"
                current -> "●"
                else -> "○"
            },
            style = MaterialTheme.typography.titleMedium,
            color = if (completed || current) {
                MaterialTheme.colorScheme.primary
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
            fontWeight = FontWeight.Bold,
        )

        Column(
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = if (current) FontWeight.ExtraBold else FontWeight.Bold,
                color = if (current) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
            )

            if (current || completed) {
                Text(
                    description,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
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
        "공식 문서를 기준으로 지금 할 수 있는 조치를 안내해드려요."

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

    LiquidGlassPanel(
        modifier = Modifier.fillMaxWidth(),
        strong = !dangerous,
        danger = dangerous,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 165.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                StatusBadge(
                    guidance.riskLevel,
                    guidance.usageStatus,
                )

                Text(
                    if (noEvidence) {
                        "공식 근거 확인이 필요해요"
                    } else {
                        "지금 필요한 안내를 확인하세요"
                    },
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Black,
                )
            }

            Image(
                painter = painterResource(R.drawable.mascot_customer),
                contentDescription = "안전 안내 캐릭터",
                modifier = Modifier.size(125.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }

    if (guidance.nextAction.isNotBlank()) {
        SectionCard(
            "지금 해야 할 행동",
            isDanger = dangerous,
        ) {
            Text(
                guidance.nextAction,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.ExtraBold,
            )
        }
    }

    val showUsage =
        guidance.usageMessage.isNotBlank() ||
            guidance.restrictedFunctions.isNotEmpty() ||
            safetyCritical

    if (showUsage) {
        SectionCard(
            "사용 가능 여부",
            isDanger = dangerous,
        ) {
            StatusBadge(
                guidance.riskLevel,
                guidance.usageStatus,
            )

            if (guidance.usageMessage.isNotBlank()) {
                Text(guidance.usageMessage)
            }

            if (guidance.restrictedFunctions.isNotEmpty()) {
                Text(
                    "사용 제한 기능",
                    fontWeight = FontWeight.Bold,
                )
                BulletList(guidance.restrictedFunctions)
            }
        }
    }

    if (guidance.safeActions.isNotEmpty()) {
        SectionCard(
            "안전 행동",
            isDanger = dangerous,
        ) {
            BulletList(guidance.safeActions)
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

    if (guidance.evidence.isNotEmpty()) {
        SectionCard("공식 근거") {
            Text(
                "공식 문서에서 확인된 내용만 보여드려요.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            guidance.evidence.forEach {
                EvidenceCard(it)
            }
        }
    }

    if (guidance.symptomSummary.isNotBlank()) {
        SectionCard("입력한 증상 요약") {
            Text(guidance.symptomSummary)
        }
    }

    if (guidance.prohibitedActions.isNotEmpty()) {
        SectionCard(
            "하지 말아야 할 행동",
            isDanger = dangerous,
        ) {
            BulletList(guidance.prohibitedActions)
        }
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
            fontWeight = FontWeight.Black,
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
