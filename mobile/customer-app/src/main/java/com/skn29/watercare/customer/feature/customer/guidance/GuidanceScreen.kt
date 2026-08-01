package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.GuidanceDisplayModel
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.RiskLevel
import com.skn29.watercare.core.model.UsageGuidanceStatus
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.theme.WaterOrange
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.*

@Composable
fun GuidanceScreen(
    inquiryId: String,
    scenario: MockScenario,
    onBack: () -> Unit,
    onRequestConsultation: () -> Unit,
    onDone: () -> Unit,
) {
    val viewModel: GuidanceViewModel = viewModel(
        factory = VmFactory {
            GuidanceViewModel(inquiryId, scenario, WaterCareCore.customerCareRepository)
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()
    var consultationNotice by remember { mutableStateOf(false) }
    val requestConsultation = {
        consultationNotice = true
        onRequestConsultation()
    }

    WaterCareScreen(title = "안전 안내", onBack = onBack) {
        when (val current = state) {
            GuidanceUiState.Loading -> LoadingBlock("검증된 고객용 안내를 불러오는 중입니다")
            is GuidanceUiState.Content -> GuidanceContent(
                guidance = current.guidance,
                noEvidence = false,
                onRetry = viewModel::load,
                onRequestConsultation = requestConsultation,
                onDone = onDone,
            )
            is GuidanceUiState.NoEvidence -> GuidanceContent(
                guidance = current.guidance,
                noEvidence = true,
                onRetry = viewModel::load,
                onRequestConsultation = requestConsultation,
                onDone = onDone,
            )
            is GuidanceUiState.AiFailure -> FailureFallback(
                title = "AI 안내 생성 실패",
                message = current.message,
                retryable = current.retryable,
                onRetry = viewModel::load,
                onRequestConsultation = requestConsultation,
            )
            is GuidanceUiState.NetworkFailure -> FailureFallback(
                title = "네트워크 연결 실패",
                message = current.message,
                retryable = current.retryable,
                onRetry = viewModel::load,
                onRequestConsultation = requestConsultation,
            )
            is GuidanceUiState.Error -> ErrorCard(current.message, if (current.retryable) viewModel::load else null)
        }
        if (consultationNotice) {
            SectionCard("상담 요청") {
                Text("상담 전환 화면이 확인되었습니다. 실제 Endpoint가 제공되기 전에는 중복 요청을 보내지 않습니다.")
            }
        }
    }
}

@Composable
fun GuidanceContent(
    guidance: GuidanceDisplayModel,
    noEvidence: Boolean,
    onRetry: () -> Unit,
    onRequestConsultation: () -> Unit,
    onDone: () -> Unit,
) {
    val dangerous = guidance.requiresConsultation ||
        guidance.riskLevel == RiskLevel.DANGER ||
        guidance.usageStatus == UsageGuidanceStatus.TOTAL_STOP ||
        guidance.usageStatus == UsageGuidanceStatus.PENDING_CONSULTATION ||
        noEvidence

    Surface(
        shape = RoundedCornerShape(30.dp),
        color = if (dangerous) MaterialTheme.colorScheme.tertiaryContainer else MaterialTheme.colorScheme.primaryContainer,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().heightIn(min = 165.dp).padding(18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusBadge(guidance.riskLevel, guidance.usageStatus)
                Text(
                    if (noEvidence) "공식 근거 확인이 필요해요" else "지금 해야 할 행동을 확인하세요",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.ExtraBold,
                )
                Text("문의번호 ${guidance.inquiryCode}", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Image(
                painter = painterResource(R.drawable.mascot_customer),
                contentDescription = "안전 안내 캐릭터",
                modifier = Modifier.size(125.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }

    SectionCard("1. 지금 해야 할 행동") {
        Text(guidance.nextAction, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
    }

    SectionCard("2. 사용 가능 여부") {
        StatusBadge(guidance.riskLevel, guidance.usageStatus)
        Text(guidance.usageMessage)
        if (guidance.restrictedFunctions.isNotEmpty()) {
            Text("사용 제한 기능", fontWeight = FontWeight.Bold)
            BulletList(guidance.restrictedFunctions)
        }
    }

    SectionCard("3. 안전 행동") {
        BulletList(
            guidance.safeActions,
            emptyText = if (noEvidence) "근거가 없어 자가조치를 추정하지 않습니다." else "추가 안전조치가 없습니다.",
        )
    }

    SectionCard("4. 상담이 필요한 경우") {
        BulletList(guidance.escalationConditions)
    }

    SectionCard("5. 공식 근거") {
        if (guidance.evidence.isEmpty()) {
            Text("표시 가능한 공식 근거가 없습니다. 판단을 보류하고 상담 확인을 우선합니다.")
            OutlinedButton(onClick = onRetry, modifier = Modifier.fillMaxWidth()) { Text("근거 다시 확인") }
        } else guidance.evidence.forEach { EvidenceCard(it) }
    }

    SectionCard("6. 입력한 증상 요약") {
        Text(guidance.symptomSummary)
    }

    SectionCard("7. 하지 말아야 할 행동") {
        BulletList(guidance.prohibitedActions)
    }

    if (dangerous) {
        Button(
            onClick = onRequestConsultation,
            modifier = Modifier.fillMaxWidth().height(54.dp).testTag("requestConsultation"),
            colors = ButtonDefaults.buttonColors(containerColor = WaterOrange),
        ) { Text("상담 요청하기", fontWeight = FontWeight.Bold) }
        Text(
            "위험·상담 필수·근거 없음 상태에서는 해결됨 또는 문의 종료 버튼을 표시하지 않습니다.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    } else {
        guidance.allowedActions.forEach { action ->
            WorkflowActionButton(
                action = action,
                onClick = if (action == "REQUEST_CONSULTATION") onRequestConsultation else onDone,
            )
        }
    }
}

@Composable
private fun FailureFallback(
    title: String,
    message: String,
    retryable: Boolean,
    onRetry: () -> Unit,
    onRequestConsultation: () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(28.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
            Text("입력값은 유지되며 내부 오류나 Stack Trace는 표시하지 않습니다.")
        }
    }
    ErrorCard(message, if (retryable) onRetry else null)
    Button(
        onClick = onRequestConsultation,
        modifier = Modifier.fillMaxWidth(),
        colors = ButtonDefaults.buttonColors(containerColor = WaterOrange),
    ) { Text("상담으로 전환") }
}
