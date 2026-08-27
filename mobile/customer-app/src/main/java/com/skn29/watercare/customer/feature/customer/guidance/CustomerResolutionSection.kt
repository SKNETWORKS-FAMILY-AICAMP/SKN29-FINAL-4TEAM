package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import com.skn29.watercare.core.ui.components.LoadingBlock
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
    onUnresolved: () -> Unit,
    onRetry: () -> Unit,
    onDone: () -> Unit,
) {
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
                        "?? ??: " +
                            consultationResult
                                .usageGuidanceDisplayLabel
                    )

                    Text(
                        "?? ??: " +
                            KoreanDateTimeFormatter.format(
                                consultationResult.completedAt
                            ),
                        style =
                            MaterialTheme.typography.bodySmall,
                    )
                } else {
                    LiquidGlassPill("?? ?? ??")
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
                    LiquidGlassButton(
                        text = "아직 해결되지 않았어요",
                        onClick = onUnresolved,
                        accent = false,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag(
                                "reportUnresolved"
                            ),
                    )
                }
            }

            is CustomerResolutionUiState.Submitting ->
                LoadingBlock(
                    "처리 결과를 저장하고 있어요"
                )

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

            is CustomerResolutionUiState.Error ->
                ErrorCard(
                    state.message,
                    if (state.retryable) {
                        onRetry
                    } else {
                        null
                    },
                )
        }
    }
}
