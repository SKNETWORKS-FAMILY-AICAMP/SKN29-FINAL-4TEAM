package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.model.CustomerInquiryQuestion
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryLabels
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.core.ui.components.LoadingBlock
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
        FollowUpUiState.Loading -> LoadingBlock("몇 가지만 더 확인할게요")

        is FollowUpUiState.Empty -> SectionCard("확인할 내용") {
            Column(
                modifier = Modifier.testTag("followUpEmpty"),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                LiquidGlassPill("확인 완료")
                Text("지금은 더 확인할 내용이 없어요.")
                SnapshotLine(state.snapshot.statusCode, state.snapshot.stateVersion)
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
            LoadingBlock("추가 답변을 저장하는 중입니다")
        }

        is FollowUpUiState.Success -> {
            SectionCard("답변을 확인했어요") {
                LiquidGlassPill("답변 저장 완료")
                Text(state.message)
                if (state.idempotentReplay) {
                    Text(
                        "이미 보낸 답변을 다시 확인했어요.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                SnapshotLine(state.snapshot.statusCode, state.snapshot.stateVersion)
            }
            if (state.questions.isEmpty()) {
                SectionCard("확인할 내용") {
                    Column(modifier = Modifier.testTag("followUpEmpty")) {
                        Text("지금은 더 확인할 내용이 없어요.")
                    }
                }
            } else {
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
                    Text(state.message)
                    SnapshotLine(state.snapshot.statusCode, state.snapshot.stateVersion)
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
                    Text(state.message)
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
            ErrorCard(
                state.message,
                if (state.retryable && state.questions.isEmpty()) onReload else null,
            )
            if (state.snapshot != null && state.questions.isNotEmpty()) {
                Column(modifier = Modifier.testTag("followUpError")) {
                    FollowUpForm(
                        state.snapshot.statusCode,
                        state.snapshot.stateVersion,
                        state.questions,
                        state.drafts,
                        submitAllowed = state.snapshot?.let(::snapshotCanSubmit) ?: false,
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
    snapshotStatus: String,
    snapshotVersion: Int,
    questions: List<CustomerInquiryQuestion>,
    drafts: Map<String, FollowUpDraft>,
    submitAllowed: Boolean,
    submitting: Boolean,
    showSubmit: Boolean,
    onTextChange: (String, String) -> Unit,
    onSelectOption: (String, String) -> Unit,
    onSubmit: () -> Unit,
) {
    SectionCard("확인할 내용") {
        Column(
            modifier = Modifier.fillMaxWidth().testTag("followUpQuestions"),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            SnapshotLine(snapshotStatus, snapshotVersion)
            questions.forEachIndexed { index, question ->
                val draft = drafts[question.questionId] ?: FollowUpDraft()
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "${index + 1}. ${question.prompt}",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
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
                        )
                        question.isSingleChoice -> question.options.forEachIndexed { optionIndex, option ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                RadioButton(
                                    selected = draft.selectedOption == option.value,
                                    onClick = { onSelectOption(question.questionId, option.value) },
                                    enabled = !submitting,
                                    modifier = Modifier.testTag(
                                        "followUpOption_${question.questionId}_$optionIndex"
                                    ),
                                )
                                Text(option.label)
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
                    text = "답변 보내기",
                    onClick = onSubmit,
                    enabled =
                        submitAllowed &&
                            !submitting &&
                            allAnswersReady(questions, drafts),
                    accent = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("submitFollowUpAnswers"),
                )
            }
        }
    }
}

@Composable
private fun SnapshotLine(statusCode: String, _stateVersion: Int) {
    Text(
        "현재 진행 상황 · ${InquiryLabels.status(statusCode)}",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
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
