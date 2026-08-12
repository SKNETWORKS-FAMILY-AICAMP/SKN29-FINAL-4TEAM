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
        FollowUpUiState.Loading -> LoadingBlock("추가 질문을 확인하는 중입니다")

        is FollowUpUiState.Empty -> SectionCard("추가 질문") {
            Column(
                modifier = Modifier.testTag("followUpEmpty"),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                LiquidGlassPill("확인 완료")
                Text("현재 추가로 답변할 질문이 없습니다.")
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
            SectionCard("추가 답변 반영 완료") {
                LiquidGlassPill("Backend 반영")
                Text(state.message)
                if (state.idempotentReplay) {
                    Text(
                        "동일 요청의 기존 처리 결과를 안전하게 재사용했습니다.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                SnapshotLine(state.snapshot.statusCode, state.snapshot.stateVersion)
            }
            if (state.questions.isEmpty()) {
                SectionCard("추가 질문") {
                    Column(modifier = Modifier.testTag("followUpEmpty")) {
                        Text("현재 추가로 답변할 질문이 없습니다.")
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
            SectionCard("문의 상태가 변경되었습니다") {
                Column(
                    modifier = Modifier.testTag("followUpConflict"),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(state.message)
                    SnapshotLine(state.snapshot.statusCode, state.snapshot.stateVersion)
                    Text(
                        "작성한 답변은 유지했습니다. 최신 질문을 확인한 뒤 직접 재시도해 주세요.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    LiquidGlassButton(
                        text = "최신 상태로 추가 답변 다시 제출",
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
            SectionCard("중복 요청 충돌") {
                Column(
                    modifier = Modifier.testTag("followUpDuplicateConflict"),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(state.message)
                    Text(
                        "같은 멱등 Key를 자동으로 다시 사용하지 않습니다. 답변을 실제로 수정하면 새 사용자 의도로 다시 제출할 수 있습니다.",
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
    SectionCard("추가 질문") {
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
                            label = { Text("답변 입력") },
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
                            "지원하지 않는 질문 유형입니다. 임의 입력을 생성하지 않습니다.",
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            }
            if (showSubmit) {
                LiquidGlassButton(
                    text = "추가 답변 제출",
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
private fun SnapshotLine(statusCode: String, stateVersion: Int) {
    Text(
        "현재 문의 · ${InquiryLabels.status(statusCode)} ($statusCode) · v$stateVersion",
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
