@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package com.skn29.watercare.customer.feature.customer.intake

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPanel
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.theme.GlassBorder
import com.skn29.watercare.core.ui.theme.GlassFill
import com.skn29.watercare.core.ui.theme.GlassFillStrong
import com.skn29.watercare.core.ui.theme.Water100
import com.skn29.watercare.core.ui.theme.Water300
import com.skn29.watercare.core.ui.theme.Water700
import com.skn29.watercare.customer.BuildConfig
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun SymptomIntakeScreen(
    subscriptionId: String,
    onBack: () -> Unit,
    onCompleted: (IntakeSubmission) -> Unit,
    onAuthExpired: () -> Unit,
) {
    val viewModel: SymptomIntakeViewModel = viewModel(
        factory = VmFactory { extras ->
            SymptomIntakeViewModel(
                subscriptionId = subscriptionId,
                repository = WaterCareCore.customerCareRepository,
                savedStateHandle = extras.createSavedStateHandle(),
            )
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.completed) {
        state.completed?.let {
            onCompleted(it)
            viewModel.consumeCompletion()
        }
    }

    LaunchedEffect(state.errorKind) {
        if (state.errorKind == IntakeErrorKind.AUTH_EXPIRED) {
            viewModel.consumeAuthExpired()
            onAuthExpired()
        }
    }

    SymptomIntakeContent(
        state = state,
        onBack = onBack,
        onEntryModeChange = viewModel::updateEntryMode,
        onToggleSymptom = viewModel::toggleSymptom,
        onRawTextChange = viewModel::updateRawText,
        onOccurrenceConditionChange = viewModel::updateOccurrenceCondition,
        onDisplayTextChange = viewModel::updateDisplayText,
        onScenarioChange = viewModel::updateScenario,
        onRetry = viewModel::submit,
        onSubmit = viewModel::submit,
    )
}

@Composable
fun SymptomIntakeContent(
    state: SymptomIntakeUiState,
    onBack: () -> Unit,
    onEntryModeChange: (EntryMode) -> Unit,
    onToggleSymptom: (SymptomTopic) -> Unit,
    onRawTextChange: (String) -> Unit,
    onOccurrenceConditionChange: (String) -> Unit,
    onDisplayTextChange: (String) -> Unit,
    onScenarioChange: (MockScenario?) -> Unit,
    onRetry: () -> Unit,
    onSubmit: () -> Unit,
) {
    val hasConflict = state.errorKind == IntakeErrorKind.CONFLICT
    val visibleConflictActions = state.conflictAllowedActions
        .filter { it.isKnownForIntakeConflict() }
    val retrySubmitAction = visibleConflictActions
        .firstOrNull { it.isRetrySubmitAction() }

    WaterCareScreen(title = "문진 시작", onBack = onBack) {
        LiquidGlassPanel(strong = true) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 150.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(7.dp),
                ) {
                    Text(
                        "어떤 문제가 있나요?",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Black,
                    )
                    Text(
                        "증상은 복수로 선택할 수 있고, 모르는 오류 코드는 그대로 전달합니다.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Image(
                    painter = painterResource(R.drawable.mascot_customer),
                    contentDescription = "문진 안내 캐릭터",
                    modifier = Modifier.size(115.dp),
                    contentScale = ContentScale.Fit,
                )
            }
        }

        SectionCard("문의 유형") {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                EntryMode.entries.forEach { mode ->
                    LiquidFilterChip(
                        selected = state.entryMode == mode,
                        onClick = { onEntryModeChange(mode) },
                        label = if (mode == EntryMode.CARE_PRECHECK) {
                            "케어 사전 문진"
                        } else {
                            "일반 문의"
                        },
                    )
                }
            }
        }

        SectionCard("대표 증상 · 복수 선택") {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SymptomTopic.entries.forEach { topic ->
                    LiquidFilterChip(
                        selected = topic in state.selectedSymptoms,
                        onClick = { onToggleSymptom(topic) },
                        label = topic.label,
                    )
                }
            }
        }

        OutlinedTextField(
            value = state.rawText,
            onValueChange = onRawTextChange,
            label = { Text("증상을 자세히 적어 주세요") },
            supportingText = {
                Text(
                    state.rawTextError
                        ?: "증상 설명은 필수입니다. ${state.rawText.length}/5000"
                )
            },
            isError = state.rawTextError != null,
            minLines = 4,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("rawText"),
            shape = RoundedCornerShape(18.dp),
            colors = liquidTextFieldColors(),
        )

        OutlinedTextField(
            value = state.occurrenceCondition,
            onValueChange = onOccurrenceConditionChange,
            label = { Text("언제, 어떤 상황에서 발생했나요?") },
            placeholder = { Text("예: 냉수 출수 시, 설치 후 3일째부터") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = liquidTextFieldColors(),
        )

        OutlinedTextField(
            value = state.displayText,
            onValueChange = onDisplayTextChange,
            label = { Text("제품 표시 문구·오류 코드") },
            supportingText = {
                Text("확인되지 않은 코드는 앱에서 추정하지 않습니다.")
            },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = liquidTextFieldColors(),
        )

        if (BuildConfig.SHOW_DEVELOPER_TOOLS) {

        SectionCard("개발 검증 시나리오") {
            Text(
                "선택하지 않으면 입력 내용으로 안전하게 판단합니다.",
                style = MaterialTheme.typography.bodySmall,
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                LiquidFilterChip(
                    selected = state.forcedScenario == null,
                    onClick = { onScenarioChange(null) },
                    label = "자동",
                )
                MockScenario.entries.forEach { scenario ->
                    LiquidFilterChip(
                        selected = state.forcedScenario == scenario,
                        onClick = { onScenarioChange(scenario) },
                        label = scenario.name,
                    )
                }
            }
        }
        }

        state.globalError
            ?.takeIf { state.errorKind != IntakeErrorKind.AUTH_EXPIRED }
            ?.let { message ->
                Text(
                    text = state.errorKind?.displayName
                        ?: IntakeErrorKind.UNKNOWN.displayName,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.error,
                )
                ErrorCard(
                    message = message,
                    onRetry = if (state.retryable) onRetry else null,
                )
            }

        if (
            state.conflictStatus != null ||
            state.conflictStateVersion != null ||
            state.conflictAllowedActions.isNotEmpty()
        ) {
            SectionCard("최신 업무 상태 · 충돌 확인") {
                state.conflictStatus?.let {
                    Text("현재 상태 · $it")
                }
                state.conflictStateVersion?.let {
                    Text("버전 · $it")
                }

                if (visibleConflictActions.isNotEmpty()) {
                    Text(
                        "Backend가 허용한 작업",
                        fontWeight = FontWeight.Bold,
                    )
                    visibleConflictActions.forEach { action ->
                        Text("• ${action.displayLabel}")
                    }
                }

                if (
                    visibleConflictActions.any {
                        !it.isRetrySubmitAction()
                    }
                ) {
                    Text(
                        "현재 화면에서 지원하지 않는 작업은 임의로 실행하지 않습니다.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                retrySubmitAction?.let { action ->
                    LiquidGlassButton(
                        text = action.displayLabel,
                        onClick = onRetry,
                        enabled = !state.isSubmitting,
                        accent = true,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("retrySubmitAfterConflict"),
                    )
                }

                Text(
                    "작성한 입력은 유지되었습니다.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }

        if (state.isSubmitting) {
            LoadingBlock("입력 내용을 안전하게 제출하고 있습니다")
        }

        LiquidGlassButton(
            text = when {
                state.isSubmitting -> "제출 중"
                hasConflict -> "최신 상태 확인 필요"
                else -> "안내 결과 확인"
            },
            onClick = onSubmit,
            enabled = !state.isSubmitting && !hasConflict,
            accent = true,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("submitIntake"),
        )
    }
}

@Composable
private fun LiquidFilterChip(
    selected: Boolean,
    onClick: () -> Unit,
    label: String,
) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label) },
        colors = FilterChipDefaults.filterChipColors(
            containerColor = GlassFillStrong.copy(alpha = 0.72f),
            selectedContainerColor = Water700.copy(alpha = 0.94f),
            labelColor = Water700,
            selectedLabelColor = Color.White,
        ),
    )
}

@Composable
private fun liquidTextFieldColors() =
    OutlinedTextFieldDefaults.colors(
        focusedContainerColor = GlassFillStrong.copy(alpha = 0.94f),
        unfocusedContainerColor = GlassFillStrong.copy(alpha = 0.72f),
        disabledContainerColor = GlassFill,
        focusedBorderColor = Water700,
        unfocusedBorderColor = Water300.copy(alpha = 0.82f),
        cursorColor = Water700,
        focusedLabelColor = Water700,
        unfocusedLabelColor = Water700.copy(alpha = 0.78f),
    )
