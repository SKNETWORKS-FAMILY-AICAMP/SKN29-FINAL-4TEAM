package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryLabels
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.WorkflowActionButton

@Composable
internal fun FollowUpCancelSection(
    snapshot: CustomerInquirySnapshot?,
    cancelState: CancelInquiryUiState,
    onConfirmCancel: (Int) -> Unit,
    onRetryConflict: () -> Unit,
    onRetryFailure: (Int) -> Unit,
    onReloadLatest: () -> Unit,
    onCancelledDone: () -> Unit,
) {
    var showDialog by
        remember {
            mutableStateOf(false)
        }

    val cancelAction =
        snapshot
            ?.allowedActions
            ?.firstOrNull {
                it.normalizedCode ==
                    InquiryActionLabels.CANCEL_INQUIRY
            }

    val cancelAllowed =
        snapshot != null &&
            canCancelInquiry(
                statusCode =
                    snapshot.statusCode,
                stateVersion =
                    snapshot.stateVersion,
                allowedActions =
                    snapshot.allowedActions,
            )

    if (
        cancelAllowed &&
        cancelAction != null &&
        cancelState is CancelInquiryUiState.Idle
    ) {
        SectionCard("문의 취소") {
            WorkflowActionButton(
                action = cancelAction,
                enabled = true,
                onClick = {
                    showDialog = true
                },
            )

            Text(
                "진행 중인 문의는 상황에 따라 취소할 수 있어요.",
                style =
                    MaterialTheme.typography
                        .bodySmall,
                color =
                    MaterialTheme.colorScheme
                        .onSurfaceVariant,
            )
        }
    }

    when (val current = cancelState) {
        CancelInquiryUiState.Idle ->
            Unit

        CancelInquiryUiState.Cancelling ->
            Unit

        is CancelInquiryUiState.Success ->
            SectionCard("문의 취소 완료") {
                LiquidGlassPill("취소됨")

                Text(
                    "문의가 취소됐어요.",
                    style =
                        MaterialTheme.typography
                            .titleMedium,
                    fontWeight =
                        FontWeight.Bold,
                    modifier =
                        Modifier.testTag(
                            "cancelledFollowUpInquiry"
                        ),
                )

                Text(
                    "\uC0C8\uB85C\uC6B4 \uBB38\uC758\uB97C "
                        + "\uCC98\uC74C\uBD80\uD130 \uC791\uC131\uD560 "
                        + "\uC218 \uC788\uC5B4\uC694.",
                    style =
                        MaterialTheme.typography
                            .bodySmall,
                )

                if (current.idempotentReplay) {
                    Text(
                        "문의 취소가 이미 처리되어 있어요.",
                        style =
                            MaterialTheme.typography
                                .bodySmall,
                    )
                }

                LiquidGlassButton(
                    text = "\uC0C8 \uBB38\uC758 \uC791\uC131\uD558\uAE30",
                    onClick =
                        onCancelledDone,
                    accent = true,
                    modifier =
                        Modifier.fillMaxWidth(),
                )
            }

        is CancelInquiryUiState.Conflict ->
            SectionCard(
                "문의 내용이 변경됐어요"
            ) {
                Text(
                    "문의 내용이 변경됐어요. 최신 상태를 확인해주세요."
                )

                current.currentStatus
                    ?.takeIf(String::isNotBlank)
                    ?.let {
                        Text(
                            InquiryLabels.status(it),
                            fontWeight =
                                FontWeight.Bold,
                        )
                    }

                if (current.canRetry) {
                    LiquidGlassButton(
                        text =
                            "문의 취소 다시 시도",
                        onClick =
                            onRetryConflict,
                        accent = false,
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .testTag(
                                    "retryFollowUpCancelAfterConflict"
                                ),
                    )
                } else {
                    Text(
                        "현재 상태에서는 문의를 취소할 수 없습니다.",
                        style =
                            MaterialTheme.typography
                                .bodySmall,
                    )

                    LiquidGlassButton(
                        text =
                            "최신 상태 확인",
                        onClick =
                            onReloadLatest,
                        accent = false,
                        modifier =
                            Modifier.fillMaxWidth(),
                    )
                }
            }

        is CancelInquiryUiState.Error ->
            ErrorCard(
                "문의 취소를 처리하지 못했어요. 잠시 후 다시 시도해주세요.",
                if (
                    current.retryable &&
                    cancelAllowed &&
                    snapshot != null
                ) {
                    {
                        onRetryFailure(
                            snapshot.stateVersion
                        )
                    }
                } else {
                    null
                },
            )
    }

    if (
        showDialog &&
        cancelAllowed &&
        snapshot != null &&
        cancelAction != null &&
        cancelState is CancelInquiryUiState.Idle
    ) {
        AlertDialog(
            onDismissRequest = {
                showDialog = false
            },
            title = {
                Text(
                    "문의를 취소할까요?"
                )
            },
            text = {
                Text(
                    cancelAction
                        .confirmationMessage
                        ?.takeIf(
                            String::isNotBlank
                        )
                        ?: "취소 후에는 현재 문의 흐름을 계속 진행할 수 없습니다."
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showDialog = false

                        onConfirmCancel(
                            snapshot.stateVersion
                        )
                    },
                    modifier =
                        Modifier.testTag(
                            "confirmCancelFollowUpInquiry"
                        ),
                ) {
                    Text("문의 취소")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        showDialog = false
                    },
                    modifier =
                        Modifier.testTag(
                            "dismissCancelFollowUpInquiry"
                        ),
                ) {
                    Text("돌아가기")
                }
            },
        )
    }
}
