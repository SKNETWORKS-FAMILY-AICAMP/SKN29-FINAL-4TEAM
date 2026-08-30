@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package com.skn29.watercare.customer.feature.customer.intake

import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.Spring
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
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
import com.skn29.watercare.core.ui.theme.GlassBorder
import com.skn29.watercare.core.ui.theme.GlassFill
import com.skn29.watercare.core.ui.theme.GlassFillStrong
import com.skn29.watercare.core.ui.theme.Water100
import com.skn29.watercare.core.ui.theme.Water300
import com.skn29.watercare.core.ui.theme.Water700
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.CustomerErrorState
import com.skn29.watercare.customer.feature.shared.CustomerSubmittingState
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun SymptomIntakeScreen(
    subscriptionId: String,
    initialTopic: SymptomTopic? = null,
    initialRawText: String = "",
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

    LaunchedEffect(
        initialTopic,
        initialRawText,
    ) {
        viewModel.applyInitialPreset(
            topic = initialTopic,
            rawText = initialRawText,
        )
    }

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

    var showRawTextRequiredDialog by
        remember {
            mutableStateOf(false)
        }

    if (showRawTextRequiredDialog) {
        AlertDialog(
            onDismissRequest = {
                showRawTextRequiredDialog = false
            },
            title = {
                Text(
                    "\uC99D\uC0C1 \uC124\uBA85\uC774 \uD544\uC694\uD574\uC694"
                )
            },
            text = {
                Text(
                    "\uC99D\uC0C1 \uC124\uBA85\uC744 \uC785\uB825\uD55C \uB4A4 \uB2E4\uC2DC \uC811\uC218\uD574\uC8FC\uC138\uC694."
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showRawTextRequiredDialog =
                            false
                    },
                ) {
                    Text(
                        "\uD655\uC778"
                    )
                }
            },
        )
    }

    WaterCareScreen(title = "불편한 점 접수", onBack = onBack) {
        LiquidGlassPanel(
            modifier = Modifier
                .fillMaxWidth()
                .testTag("intakeHero"),
            strong = true,
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 132.dp),
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
                        "현재 불편한 점과 가장 가까운 항목을 선택해주세요.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Image(
                    painter = painterResource(R.drawable.mascot_customer),
                    contentDescription = "증상 접수 안내",
                    modifier = Modifier.size(100.dp),
                    contentScale = ContentScale.Fit,
                )
            }
        }

        SectionCard("불편한 점 선택") {
            Text(
                "불편한 점이 여러 개라면 모두 선택할 수 있어요.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                listOf(
                    SymptomTopic.LOW_FLOW,
                    SymptomTopic.TASTE_ODOR,
                    SymptomTopic.OTHER,
                    SymptomTopic.LEAK,
                    SymptomTopic.TEMPERATURE,
                ).forEach { topic ->
                    LiquidFilterChip(
                        selected = topic in state.selectedSymptoms,
                        onClick = { onToggleSymptom(topic) },
                        label = customerSymptomLabel(topic),
                    )
                }
            }
        }

        OutlinedTextField(
            value = state.rawText,
            onValueChange = onRawTextChange,
            label = { Text("조금 더 알려주세요") },
            placeholder = {
                Text("예: 어제부터 물이 평소보다 약하게 나와요")
            },
            supportingText = {
                Text(
                    state.rawTextError
                        ?: "짧게 적어주셔도 괜찮아요. ${state.rawText.length}/5000"
                )
            },
            isError = state.rawTextError != null,
            minLines = 3,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("rawText"),
            shape = RoundedCornerShape(18.dp),
            colors = liquidTextFieldColors(),
        )

        OutlinedTextField(
            value = state.occurrenceCondition,
            onValueChange = onOccurrenceConditionChange,
            label = { Text("언제 주로 발생하나요? (선택)") },
            placeholder = { Text("예: 냉수를 사용할 때, 어제 저녁부터") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(18.dp),
            colors = liquidTextFieldColors(),
        )

        state.globalError
            ?.takeIf {
                state.errorKind !=
                    IntakeErrorKind.AUTH_EXPIRED
            }
            ?.let { message ->
                val isOffline =
                    state.errorKind ==
                        IntakeErrorKind.NETWORK

                // Network error는 서버 오류와 다르다.
                // 사용자가 스스로 복구할 수 있는 문제이므로
                // "인터넷 연결 확인" 행동을 명확하게 안내한다.
                CustomerErrorState(
                    title =
                        if (isOffline) {
                            "인터넷 연결을 확인해주세요"
                        } else {
                            "접수를 완료하지 못했어요"
                        },
                    message =
                        customerIntakeErrorMessage(
                            kind = state.errorKind,
                            originalMessage = message,
                        ),
                    onRetry =
                        if (state.retryable) {
                            onRetry
                        } else {
                            null
                        },
                )
            }

        if (hasConflict) {
            SectionCard("접수 상태가 변경됐어요") {
                Text(
                    "작성한 내용은 그대로 보관했어요. 최신 상태를 확인한 뒤 다시 시도해주세요."
                )

                retrySubmitAction?.let { action ->
                    LiquidGlassButton(
                        text = "다시 접수하기",
                        onClick = onRetry,
                        enabled = !state.isSubmitting,
                        accent = true,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("retrySubmitAfterConflict"),
                    )
                }
            }
        }

        if (state.isSubmitting) {
            // Submit 후 API 응답이 올 때까지
            // "보내는 중"임을 사용자에게 명시적으로 알린다.
            // 아래 버튼은 기존처럼 disabled되므로
            // 여러 번 눌러 중복 접수하는 문제도 막을 수 있다.
            CustomerSubmittingState(
                message =
                    "작성한 내용을 안전하게 접수하고 있어요.",
            )
        }

        LiquidGlassButton(
            text = when {
                state.isSubmitting -> "보내는 중"
                hasConflict -> "다시 확인해주세요"
                else -> "불편한 점 접수하기"
            },
            onClick = {
                if (state.rawText.isBlank()) {
                    showRawTextRequiredDialog = true
                } else {
                    onSubmit()
                }
            },
            enabled = !state.isSubmitting && !hasConflict,
            accent = true,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("submitIntake"),
        )
    }
}

private fun customerSymptomLabel(
    topic: SymptomTopic,
): String = when (topic) {
    SymptomTopic.LOW_FLOW -> "물이 약해요"
    SymptomTopic.TASTE_ODOR -> "물맛이 이상해요"
    SymptomTopic.LEAK -> "누수가 보여요"
    SymptomTopic.TEMPERATURE -> "냉수·온수 온도가 이상해요"
    SymptomTopic.OTHER -> "소리가 나요"
}

private fun customerIntakeErrorMessage(
    kind: IntakeErrorKind?,
    originalMessage: String,
): String = when (kind) {
    IntakeErrorKind.VALIDATION ->
        "입력한 내용을 한 번 확인해주세요."
    IntakeErrorKind.CONFLICT ->
        "접수 상태가 바뀌었어요. 작성한 내용은 유지되어 있습니다."
    IntakeErrorKind.NETWORK ->
        "인터넷 연결을 확인한 뒤 다시 시도해주세요."
    IntakeErrorKind.SERVER ->
        "잠시 처리에 문제가 생겼어요. 잠시 후 다시 시도해주세요."
    IntakeErrorKind.FORBIDDEN ->
        "현재 이 문의를 처리할 수 없습니다."
    IntakeErrorKind.NOT_FOUND ->
        "필요한 정보를 찾지 못했어요. 홈에서 다시 시작해주세요."
    IntakeErrorKind.AUTH_EXPIRED ->
        "로그인이 만료됐어요. 다시 로그인해주세요."
    IntakeErrorKind.UNKNOWN, null ->
        "문제를 처리하는 중 오류가 발생했어요. 잠시 후 다시 시도해주세요."
}

@Composable
private fun LiquidFilterChip(
    selected: Boolean,
    onClick: () -> Unit,
    label: String,
) {
    val selectionScale by animateFloatAsState(
        targetValue =
            1f,
        animationSpec = spring(
            dampingRatio =
                Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessMedium,
        ),
        label = "symptomChipScale",
    )

    FilterChip(
        selected = selected,
        onClick = onClick,
        modifier = Modifier
            .heightIn(min = 50.dp)
            .graphicsLayer {
                scaleX = selectionScale
                scaleY = selectionScale
            },
        label = {
            Text(
                text = label,
                modifier = Modifier.padding(
                    horizontal = 3.dp,
                    vertical = 4.dp,
                ),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
                maxLines = 2,
            )
        },
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
