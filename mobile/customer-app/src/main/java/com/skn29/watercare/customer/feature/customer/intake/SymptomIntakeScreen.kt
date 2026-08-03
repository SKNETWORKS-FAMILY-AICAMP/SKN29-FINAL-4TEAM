@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package com.skn29.watercare.customer.feature.customer.intake

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.customer.CustomerRuntime
import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun SymptomIntakeScreen(
    subscriptionId: String,
    onBack: () -> Unit,
    onAuthExpired: () -> Unit,
    onCompleted: (IntakeSubmission) -> Unit,
) {
    val viewModel: SymptomIntakeViewModel = viewModel(
        factory = VmFactory {
            SymptomIntakeViewModel(subscriptionId, CustomerRuntime.inquiryRepository)
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.completed) {
        state.completed?.let {
            onCompleted(it)
            viewModel.consumeCompletion()
        }
    }

    LaunchedEffect(state.authExpired) {
        if (state.authExpired) {
            viewModel.consumeAuthExpiration()
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
    WaterCareScreen(title = "문진 시작", onBack = onBack) {
        Surface(shape = RoundedCornerShape(28.dp), color = MaterialTheme.colorScheme.primaryContainer) {
            Row(
                modifier = Modifier.fillMaxWidth().heightIn(min = 150.dp).padding(18.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                    Text("어떤 문제가 있나요?", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
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

        SectionCard("API 연동 상태") {
            Text("문의 생성·취소는 실제 Backend Runtime을 사용합니다.", fontWeight = FontWeight.Bold)
            Text(
                "추가 문진·Guidance·상담·문의 상세는 Backend Route 제공 전까지 Mock/Blocked입니다.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        SectionCard("문의 유형") {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                EntryMode.entries.forEach { mode ->
                    FilterChip(
                        selected = state.entryMode == mode,
                        onClick = { onEntryModeChange(mode) },
                        label = { Text(if (mode == EntryMode.CARE_PRECHECK) "케어 사전 문진" else "일반 문의") },
                    )
                }
            }
        }

        SectionCard("대표 증상 · 복수 선택") {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SymptomTopic.entries.forEach { topic ->
                    FilterChip(
                        selected = topic in state.selectedSymptoms,
                        onClick = { onToggleSymptom(topic) },
                        label = { Text(topic.label) },
                    )
                }
            }
        }

        OutlinedTextField(
            value = state.rawText,
            onValueChange = onRawTextChange,
            label = { Text("증상을 자세히 적어 주세요") },
            supportingText = {
                Text(state.rawTextError ?: "대표 증상을 선택하지 않으면 필수입니다. ${state.rawText.length}/5000")
            },
            isError = state.rawTextError != null,
            minLines = 4,
            modifier = Modifier.fillMaxWidth().testTag("rawText"),
            shape = RoundedCornerShape(18.dp),
        )

        OutlinedTextField(
            value = state.occurrenceCondition,
            onValueChange = onOccurrenceConditionChange,
            label = { Text("언제, 어떤 상황에서 발생했나요?") },
            placeholder = { Text("예: 냉수 출수 시, 설치 후 3일째부터") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
        )

        OutlinedTextField(
            value = state.displayText,
            onValueChange = onDisplayTextChange,
            label = { Text("제품 표시 문구·오류 코드") },
            supportingText = { Text("확인되지 않은 코드는 앱에서 추정하지 않습니다.") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
        )

        SectionCard("Mock/Blocked 화면 설정") {
            Text("실제 문의 접수 후 표시할 Guidance 미리보기 시나리오입니다. Backend에는 전송하지 않습니다.", style = MaterialTheme.typography.bodySmall)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = state.forcedScenario == null,
                    onClick = { onScenarioChange(null) },
                    label = { Text("자동") },
                )
                MockScenario.entries.forEach { scenario ->
                    FilterChip(
                        selected = state.forcedScenario == scenario,
                        onClick = { onScenarioChange(scenario) },
                        label = { Text(scenario.name) },
                    )
                }
            }
        }

        state.globalError?.let {
            ErrorCard(message = it, onRetry = if (state.retryable) onRetry else null)
        }

        state.correlationId?.let { correlationId ->
            SectionCard("요청 추적 정보") {
                Text("correlation_id · $correlationId", style = MaterialTheme.typography.bodySmall)
                Text("오류 문의 시 이 값만 공유하고 Token·개인정보는 공유하지 않습니다.", style = MaterialTheme.typography.bodySmall)
            }
        }

        if (
            state.conflictStatus != null ||
            state.conflictStateVersion != null ||
            state.conflictAllowedActions.isNotEmpty()
        ) {
            SectionCard("최신 업무 상태 · 충돌 확인") {
                state.conflictStatus?.let { Text("현재 상태 · $it") }
                state.conflictStateVersion?.let { Text("버전 · $it") }
                if (state.conflictAllowedActions.isNotEmpty()) {
                    Text("가능한 작업 · ${state.conflictAllowedActions.joinToString()}")
                }
                Text("작성한 입력은 유지되었습니다.", style = MaterialTheme.typography.bodySmall)
            }
        }

        if (state.isSubmitting) LoadingBlock("입력 내용을 안전하게 제출하고 있습니다")

        Button(
            onClick = onSubmit,
            enabled = !state.isSubmitting,
            modifier = Modifier.fillMaxWidth().height(54.dp).testTag("submitIntake"),
        ) {
            Text(if (state.isSubmitting) "접수 중" else "실제 문의 접수", fontWeight = FontWeight.Bold)
        }
    }
}
