package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.skn29.watercare.core.model.CustomerInquiryQuestion
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryLabels
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.customer.feature.shared.CustomerErrorState
import com.skn29.watercare.customer.feature.shared.CustomerSubmittingState
import com.skn29.watercare.customer.feature.shared.SectionCard

@Composable
fun FollowUpQuestionsSection(
    state: FollowUpUiState,
    onTextChange: (String, String) -> Unit,
    onSelectOption: (String, String) -> Unit,
    onSubmit: () -> Unit,
    onRetryConflict: () -> Unit,
    onReload: () -> Unit,
) {
    when (state) {
        FollowUpUiState.Disabled -> Unit
        FollowUpUiState.Loading -> Unit

        is FollowUpUiState.Empty -> {
            if (
                state.snapshot.statusCode
                    .trim()
                    .uppercase() ==
                "QUESTIONNAIRE_IN_PROGRESS"
            ) {
                SectionCard("답변을 분석하고 있어요") {
                    LiquidGlassPill("AI 분석 중")
                    Text(
                        "추가 답변을 반영해 맞춤 해결 안내를 준비하고 있습니다. 잠시만 기다려 주세요.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }

        is FollowUpUiState.Form -> FollowUpForm(
            state.snapshot.statusCode,
            state.snapshot.stateVersion,
            state.questions,
            state.drafts,
            submitAllowed = snapshotCanSubmit(state.snapshot),
            submitting = false,
            showSubmit = true,
            onTextChange = onTextChange,
            onSelectOption = onSelectOption,
            onSubmit = onSubmit,
        )

        is FollowUpUiState.Submitting -> {
            FollowUpForm(
                state.snapshot.statusCode,
                state.snapshot.stateVersion,
                state.questions,
                state.drafts,
                submitAllowed = snapshotCanSubmit(state.snapshot),
                submitting = true,
                showSubmit = true,
                onTextChange = onTextChange,
                onSelectOption = onSelectOption,
                onSubmit = onSubmit,
            )

            // 답변 전송 중에는 Form을 유지하되
            // 입력과 버튼은 disabled해 중복 제출을 막고,
            // 사용자에게는 현재 서버로 전송 중임을 알린다.
            CustomerSubmittingState(
                message =
                    "작성한 답변을 전송하고 있어요.",
            )
        }

        is FollowUpUiState.Processing -> {
            SectionCard("답변이 저장됐어요") {
                LiquidGlassPill("다음 단계 확인 중")
                Text(
                    "입력한 내용을 바탕으로 다음 단계를 확인하고 있어요.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }

        is FollowUpUiState.Success -> {
            if (state.questions.isNotEmpty()) {
                SectionCard("답변을 확인했어요") {
                    LiquidGlassPill("답변 저장 완료")

                    if (state.idempotentReplay) {
                        Text(
                            "이미 보낸 답변을 다시 확인했어요.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }

                FollowUpForm(
                    state.snapshot.statusCode,
                    state.snapshot.stateVersion,
                    state.questions,
                    state.drafts,
                    submitAllowed = snapshotCanSubmit(state.snapshot),
                    submitting = false,
                    showSubmit = true,
                    onTextChange = onTextChange,
                    onSelectOption = onSelectOption,
                    onSubmit = onSubmit,
                )
            }
        }
        is FollowUpUiState.Conflict -> {
            SectionCard("문의 상황이 바뀌었어요") {
                Column(
                    modifier = Modifier.testTag("followUpConflict"),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        "작성한 답변은 그대로 있어요. 현재 질문을 확인한 뒤 다시 보내주세요.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    LiquidGlassButton(
                        text = "답변 다시 보내기",
                        onClick = onRetryConflict,
                        enabled = state.canRetry && allAnswersReady(state.questions, state.drafts),
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("retryFollowUpAfterConflict"),
                    )
                }
            }
            if (state.questions.isNotEmpty()) {
                FollowUpForm(
                    state.snapshot.statusCode,
                    state.snapshot.stateVersion,
                    state.questions,
                    state.drafts,
                    submitAllowed = snapshotCanSubmit(state.snapshot),
                    submitting = false,
                    showSubmit = false,
                    onTextChange = onTextChange,
                    onSelectOption = onSelectOption,
                    onSubmit = onSubmit,
                )
            }
        }

        is FollowUpUiState.DuplicateConflict -> {
            SectionCard("이미 보낸 답변이에요") {
                Column(
                    modifier = Modifier.testTag("followUpDuplicateConflict"),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        "같은 답변이 다시 전송되지 않도록 멈췄어요. 내용을 바꾸면 다시 보낼 수 있어요.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            FollowUpForm(
                state.snapshot.statusCode,
                state.snapshot.stateVersion,
                state.questions,
                state.drafts,
                submitAllowed = snapshotCanSubmit(state.snapshot),
                submitting = false,
                showSubmit = false,
                onTextChange = onTextChange,
                onSelectOption = onSelectOption,
                onSubmit = onSubmit,
            )
        }

        is FollowUpUiState.Error -> {
            CustomerErrorState(
                title =
                    if (state.answerSubmissionFailed) {
                        "답변을 저장하지 못했어요"
                    } else {
                        "추가 질문을 확인하지 못했어요"
                    },
                message =
                    if (state.answerSubmissionFailed) {
                        "작성한 답변은 유지했어요. 잠시 후 다시 시도해주세요."
                    } else {
                        "잠시 후 다시 확인해주세요."
                    },
                onRetry =
                    if (
                        state.retryable &&
                        state.questions.isEmpty()
                    ) {
                        onReload
                    } else {
                        null
                    },
            )
            if (state.snapshot != null && state.questions.isNotEmpty()) {
                Column(modifier = Modifier.testTag("followUpError")) {
                    FollowUpForm(
                        state.snapshot.statusCode,
                        state.snapshot.stateVersion,
                        state.questions,
                        state.drafts,
                        submitAllowed = snapshotCanSubmit(state.snapshot),
                        submitting = false,
                        showSubmit = true,
                        onTextChange = onTextChange,
                        onSelectOption = onSelectOption,
                        onSubmit = onSubmit,
                    )
                }
            }
        }
    }
}

@Composable
private fun FollowUpForm(
    _snapshotStatus: String,
    _snapshotVersion: Int,
    questions: List<CustomerInquiryQuestion>,
    drafts: Map<String, FollowUpDraft>,
    submitAllowed: Boolean,
    submitting: Boolean,
    showSubmit: Boolean,
    onTextChange: (String, String) -> Unit,
    onSelectOption: (String, String) -> Unit,
    onSubmit: () -> Unit,
) {
    SectionCard("추가 질문") {
        Column(
            modifier = Modifier.fillMaxWidth().testTag("followUpQuestions"),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            questions.forEachIndexed { index, question ->
                val draft =
                    drafts[question.questionId]
                        ?: FollowUpDraft()
                Column(
                    modifier =
                        Modifier.fillMaxWidth(),
                    verticalArrangement =
                        Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        "${index + 1}. ${question.prompt}",
                        style = MaterialTheme.typography.titleSmall,
                        fontSize = 18.sp,
                        lineHeight = 24.sp,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    when {
                        question.isFreeText -> OutlinedTextField(
                            value = draft.text,
                            onValueChange = { onTextChange(question.questionId, it) },
                            enabled = !submitting,
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("followUpText_${question.questionId}"),
                            label = { Text("답변을 적어주세요") },
                            minLines = 2,
                            maxLines = 4,
                            shape = RoundedCornerShape(18.dp),
                        )
                        question.isSingleChoice -> question.options.forEachIndexed { optionIndex, option ->
                            val optionSelected =
                                draft.selectedOption ==
                                    option.value
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 48.dp)
                                    .clip(RoundedCornerShape(16.dp))
                                    .background(
                                        MaterialTheme.colorScheme.surfaceVariant.copy(
                                            alpha = 0.42f
                                        )
                                    )
                                    .padding(horizontal = 8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(7.dp),
                            ) {
                                RadioButton(
                                    selected = optionSelected,
                                    onClick = { onSelectOption(question.questionId, option.value) },
                                    enabled = !submitting,
                                    modifier = Modifier.testTag(
                                        "followUpOption_${question.questionId}_$optionIndex"
                                    ),
                                )
                                Text(
                                    text = option.label,
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.SemiBold,
                                )
                            }
                        }
                        else -> Text(
                            "이 질문은 지금 앱에서 답하기 어려워요. 다른 항목을 먼저 확인해주세요.",
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            }
            if (showSubmit) {
                LiquidGlassButton(
                    text = "문진 완료하고 계속",
                    onClick = onSubmit,
                    enabled =
                        !submitting,
                    accent = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("submitFollowUpAnswers"),
                )
            }
        }
    }
}

private fun snapshotCanSubmit(
    snapshot: com.skn29.watercare.core.model.CustomerInquirySnapshot,
): Boolean = snapshot.allowedActions.any {
    it.normalizedCode == InquiryActionLabels.SUBMIT_ANSWERS
}

private fun allAnswersReady(
    questions: List<CustomerInquiryQuestion>,
    drafts: Map<String, FollowUpDraft>,
): Boolean = questions.isNotEmpty() && questions.all { question ->
    val draft = drafts[question.questionId] ?: FollowUpDraft()
    when {
        question.isFreeText -> !question.required || draft.text.isNotBlank()
        question.isSingleChoice -> !question.required || (
            !draft.selectedOption.isNullOrBlank() &&
                question.options.any { it.value == draft.selectedOption }
            )
        else -> false
    }
}
