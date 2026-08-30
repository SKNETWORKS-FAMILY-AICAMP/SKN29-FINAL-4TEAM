package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.CustomerInquiryConsultationResult
import com.skn29.watercare.core.model.KoreanDateTimeFormatter
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.customer.feature.shared.SectionCard

@Composable
fun CustomerResolutionSection(
    statusCode: String?,
    stateVersion: Int?,
    allowedActions: List<AllowedAction>,
    consultationResult:
        CustomerInquiryConsultationResult? = null,
    state: CustomerResolutionUiState,
    onResolved: () -> Unit,
    onUnresolved: (String) -> Unit,
    onRetry: () -> Unit,
    onDone: () -> Unit,
) {
    var showUnresolvedForm by
        rememberSaveable {
            mutableStateOf(false)
        }

    var unresolvedComment by
        rememberSaveable {
            mutableStateOf("")
        }

    val normalized =
        statusCode?.trim()?.uppercase().orEmpty()

    val resolvedAction =
        allowedActions.firstOrNull {
            it.normalizedCode ==
                InquiryActionLabels
                    .SUBMIT_RESOLUTION_FEEDBACK
        }
    val unresolvedAction =
        allowedActions.firstOrNull {
            it.normalizedCode ==
                InquiryActionLabels
                    .CUSTOMER_REPORTED_UNRESOLVED
        }

    if (
        normalized != "COMPLETION_PENDING" &&
        resolvedAction == null &&
        unresolvedAction == null &&
        state !is CustomerResolutionUiState.Success
    ) return

    SectionCard("상담 처리 결과") {
        when (state) {
            CustomerResolutionUiState.Idle -> {
                if (consultationResult != null) {
                    LiquidGlassPill(
                        consultationResult.resultDisplayLabel
                    )

                    Text(
                        consultationResult.customerGuidance,
                        style =
                            MaterialTheme.typography
                                .titleMedium,
                        fontWeight = FontWeight.Bold,
                    )

                    Text(
                        "사용 상태: " +
                            consultationResult
                                .usageGuidanceDisplayLabel
                    )

                    Text(
                        "처리 완료: " +
                            KoreanDateTimeFormatter.format(
                                consultationResult.completedAt
                            ),
                        style =
                            MaterialTheme.typography.bodySmall,
                    )
                } else {
                    LiquidGlassPill("고객 확인 필요")
                }

                Text(
                    "상담 또는 방문 처리가 완료됐어요.",
                    style =
                        MaterialTheme.typography
                            .titleMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    "현재 문제가 해결됐는지 알려주세요. 고객 확인 후 담당자가 문의를 최종 마무리합니다."
                )

                if (
                    resolvedAction != null &&
                    stateVersion != null
                ) {
                    LiquidGlassButton(
                        text = "해결됐어요",
                        onClick = onResolved,
                        accent = true,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag(
                                "submitResolutionFeedback"
                            ),
                    )
                }

                if (
                    unresolvedAction != null &&
                    stateVersion != null
                ) {
                    if (!showUnresolvedForm) {
                        LiquidGlassButton(
                            text =
                                "아직 해결되지 " +
                                    "않았어요",
                            onClick = {
                                showUnresolvedForm =
                                    true
                            },
                            accent = false,
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag(
                                    "reportUnresolved"
                                ),
                        )
                    } else {
                        UnresolvedCommentForm(
                            comment =
                                unresolvedComment,
                            onCommentChange = {
                                unresolvedComment = it
                            },
                            onSubmit = {
                                onUnresolved(
                                    unresolvedComment
                                )
                            },
                            onCancel = {
                                unresolvedComment = ""
                                showUnresolvedForm =
                                    false
                            },
                            enabled = true,
                        )
                    }
                }
            }

            is CustomerResolutionUiState.Submitting ->
                Unit

            is CustomerResolutionUiState.Success -> {
                val resolved =
                    state.actionCode ==
                        InquiryActionLabels
                            .SUBMIT_RESOLUTION_FEEDBACK

                LiquidGlassPill(
                    if (resolved) {
                        "해결 확인 전달 완료"
                    } else {
                        "미해결 접수 완료"
                    }
                )
                Text(
                    if (resolved) {
                        "해결됐다는 답변을 전달했어요."
                    } else {
                        "아직 해결되지 않았다는 내용을 전달했어요."
                    },
                    style =
                        MaterialTheme.typography
                            .titleMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    if (resolved) {
                        "담당자가 확인한 뒤 문의를 최종 완료합니다."
                    } else {
                        "담당자가 확인한 뒤 필요한 후속 상담을 이어갑니다."
                    }
                )
                LiquidGlassButton(
                    text = "홈에서 상태 확인",
                    onClick = onDone,
                    accent = true,
                    modifier =
                        Modifier.fillMaxWidth(),
                )
            }

            is CustomerResolutionUiState.Error -> {
                val unresolvedFailure =
                    state.actionCode ==
                        InquiryActionLabels
                            .CUSTOMER_REPORTED_UNRESOLVED

                ErrorCard(
                    state.message,
                    if (
                        state.retryable &&
                        !unresolvedFailure
                    ) {
                        onRetry
                    } else {
                        null
                    },
                )

                if (
                    unresolvedFailure &&
                    unresolvedAction != null &&
                    stateVersion != null
                ) {
                    UnresolvedCommentForm(
                        comment =
                            unresolvedComment,
                        onCommentChange = {
                            unresolvedComment = it
                        },
                        onSubmit = {
                            onUnresolved(
                                unresolvedComment
                            )
                        },
                        onCancel = {
                            unresolvedComment = ""
                            showUnresolvedForm =
                                false
                        },
                        enabled = true,
                    )
                }
            }
        }
    }
}

@Composable
private fun UnresolvedCommentForm(
    comment: String,
    onCommentChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onCancel: () -> Unit,
    enabled: Boolean,
) {
    Text(
        text =
            "\uC5B4\uB5A4 \uBB38\uC81C\uAC00 \uC544\uC9C1 " +
                "\uB0A8\uC544 \uC788\uB098\uC694?",
        style =
            MaterialTheme.typography
                .titleSmall,
        fontWeight = FontWeight.Bold,
    )

    Text(
        text =
            "\uC0C1\uB2F4\uC0AC\uAC00 \uC774\uC804 \uC0C1\uB2F4 " +
                "\uB0B4\uC6A9\uACFC \uD568\uAED8 \uD655\uC778\uD560 " +
                "\uC218 \uC788\uB3C4\uB85D \uD604\uC7AC \uB0A8\uC544 " +
                "\uC788\uB294 \uC99D\uC0C1\uC744 \uC801\uC5B4\uC8FC\uC138\uC694.",
        style =
            MaterialTheme.typography
                .bodySmall,
    )

    OutlinedTextField(
        value = comment,
        onValueChange = { value ->
            onCommentChange(
                value.take(1000)
            )
        },
        enabled = enabled,
        label = {
            Text(
                "\uB0A8\uC544 \uC788\uB294 \uBB38\uC81C\uB97C " +
                    "\uC801\uC5B4\uC8FC\uC138\uC694"
            )
        },
        minLines = 3,
        maxLines = 6,
        modifier = Modifier
            .fillMaxWidth()
            .testTag(
                "unresolvedComment"
            ),
    )

    Text(
        text =
            "${comment.length}/1000",
        style =
            MaterialTheme.typography
                .bodySmall,
    )

    LiquidGlassButton(
        text =
            "\uD6C4\uC18D \uC0C1\uB2F4 \uC694\uCCAD\uD558\uAE30",
        onClick = onSubmit,
        enabled =
            enabled &&
                comment.trim().isNotEmpty(),
        accent = true,
        modifier = Modifier
            .fillMaxWidth()
            .testTag(
                "submitUnresolvedComment"
            ),
    )

    LiquidGlassButton(
        text = "\uCDE8\uC18C",
        onClick = onCancel,
        enabled = enabled,
        accent = false,
        modifier = Modifier
            .fillMaxWidth()
            .testTag(
                "cancelUnresolvedComment"
            ),
    )
}
