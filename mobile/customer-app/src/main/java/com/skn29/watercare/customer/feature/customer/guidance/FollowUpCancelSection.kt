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
import com.skn29.watercare.core.ui.components.LoadingBlock
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
        SectionCard("?? ??") {
            WorkflowActionButton(
                action = cancelAction,
                enabled = true,
                onClick = {
                    showDialog = true
                },
            )

            Text(
                "?? ?? ??? ??? ? ???.",
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
            LoadingBlock(
                "??? ???? ????"
            )

        is CancelInquiryUiState.Success ->
            SectionCard("?? ?? ??") {
                LiquidGlassPill("???")

                Text(
                    "??? ?????.",
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

                if (current.idempotentReplay) {
                    Text(
                        "?? ??? ?? ??? ?????.",
                        style =
                            MaterialTheme.typography
                                .bodySmall,
                    )
                }

                LiquidGlassButton(
                    text = "????",
                    onClick =
                        onCancelledDone,
                    accent = true,
                    modifier =
                        Modifier.fillMaxWidth(),
                )
            }

        is CancelInquiryUiState.Conflict ->
            SectionCard(
                "?? ??? ?????"
            ) {
                Text(
                    "?? ?? ??? ??????."
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
                            "?? ?? ?? ??",
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
                        "?? ????? ??? ??? ? ????.",
                        style =
                            MaterialTheme.typography
                                .bodySmall,
                    )

                    LiquidGlassButton(
                        text =
                            "?? ?? ??",
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
                "?? ??? ???? ????. ?? ? ?? ??????.",
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
                    "??? ??????"
                )
            },
            text = {
                Text(
                    cancelAction
                        .confirmationMessage
                        ?.takeIf(
                            String::isNotBlank
                        )
                        ?: "?? ??? ?? ??? ?? ??? ?? ??? ? ????."
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
                    Text("?? ??")
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
                    Text("????")
                }
            },
        )
    }
}
