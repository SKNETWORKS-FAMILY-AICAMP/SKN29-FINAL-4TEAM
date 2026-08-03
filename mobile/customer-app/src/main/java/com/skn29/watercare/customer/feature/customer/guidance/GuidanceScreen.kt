package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
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
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.BulletList
import com.skn29.watercare.customer.feature.shared.EvidenceCard
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.StatusBadge
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun GuidanceScreen(
    inquiryId: String,
    scenario: MockScenario,
    onBack: () -> Unit,
) {
    val viewModel: GuidanceViewModel = viewModel(
        factory = VmFactory {
            GuidanceViewModel(
                inquiryId,
                scenario,
                WaterCareCore.customerCareRepository,
            )
        },
    )
    val state by viewModel.state.collectAsStateWithLifecycle()

    WaterCareScreen(title = "안전 안내", onBack = onBack) {
        SectionCard("Mock/Blocked 화면") {
            Text(
                "Guidance와 상담 요청 Endpoint는 아직 Backend Runtime에 없습니다.",
                fontWeight = FontWeight.Bold,
            )
            Text(
                "이 화면은 UI·안전 정책 검증용 Mock이며 실제 API 연동 완료로 표시하지 않습니다.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        when (val current = state) {
            GuidanceUiState.Loading ->
                LoadingBlock("검증된 고객용 안내를 불러오는 중입니다")

            is GuidanceUiState.Content ->
                GuidanceContent(
                    guidance = current.guidance,
                    noEvidence = false,
                    onRetry = viewModel::load,
                )

            is GuidanceUiState.NoEvidence ->
                GuidanceContent(
                    guidance = current.guidance,
                    noEvidence = true,
                    onRetry = viewModel::load,
                )

            is GuidanceUiState.AiFailure ->
                FailureFallback(
                    title = "AI 안내 생성 실패",
                    message = current.message,
                    retryable = current.retryable,
                    onRetry = viewModel::load,
                )

            is GuidanceUiState.NetworkFailure ->
                FailureFallback(
                    title = "네트워크 연결 실패",
                    message = current.message,
                    retryable = current.retryable,
                    onRetry = viewModel::load,
                )

            is GuidanceUiState.Error ->
                ErrorCard(
                    current.message,
                    if (current.retryable) viewModel::load else null,
                )
        }
    }
}

@Composable
fun GuidanceContent(
    guidance: GuidanceDisplayModel,
    noEvidence: Boolean,
    onRetry: () -> Unit,
) {
    val dangerous =
        guidance.requiresConsultation ||
            guidance.riskLevel == RiskLevel.DANGER ||
            guidance.usageStatus == UsageGuidanceStatus.TOTAL_STOP ||
            guidance.usageStatus ==
                UsageGuidanceStatus.PENDING_CONSULTATION ||
            noEvidence

    Surface(
        shape = RoundedCornerShape(30.dp),
        color =
            if (dangerous) {
                MaterialTheme.colorScheme.tertiaryContainer
            } else {
                MaterialTheme.colorScheme.primaryContainer
            },
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = 165.dp)
                    .padding(18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                StatusBadge(
                    guidance.riskLevel,
                    guidance.usageStatus,
                )
                Text(
                    if (noEvidence) {
                        "공식 근거 확인이 필요해요"
                    } else {
                        "지금 해야 할 행동을 확인하세요"
                    },
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.ExtraBold,
                )
                Text(
                    "문의번호 ${guidance.inquiryCode}",
                    color =
                        MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Image(
                painter =
                    painterResource(R.drawable.mascot_customer),
                contentDescription = "안전 안내 캐릭터",
                modifier = Modifier.size(125.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }

    SectionCard("1. 지금 해야 할 행동") {
        Text(
            guidance.nextAction,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.ExtraBold,
        )
    }

    SectionCard("2. 사용 가능 여부") {
        StatusBadge(
            guidance.riskLevel,
            guidance.usageStatus,
        )
        Text(guidance.usageMessage)

        if (guidance.restrictedFunctions.isNotEmpty()) {
            Text(
                "사용 제한 기능",
                fontWeight = FontWeight.Bold,
            )
            BulletList(guidance.restrictedFunctions)
        }
    }

    SectionCard("3. 안전 행동") {
        BulletList(
            guidance.safeActions,
            emptyText =
                if (noEvidence) {
                    "근거가 없어 자가조치를 추정하지 않습니다."
                } else {
                    "추가 안전조치가 없습니다."
                },
        )
    }

    SectionCard("4. 상담이 필요한 경우") {
        BulletList(guidance.escalationConditions)
    }

    SectionCard("5. 공식 근거") {
        if (guidance.evidence.isEmpty()) {
            Text(
                "표시 가능한 공식 근거가 없습니다. 판단을 보류하고 상담 확인을 우선합니다.",
            )
            OutlinedButton(
                onClick = onRetry,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("근거 다시 확인")
            }
        } else {
            guidance.evidence.forEach { EvidenceCard(it) }
        }
    }

    SectionCard("6. 입력한 증상 요약") {
        Text(guidance.symptomSummary)
    }

    SectionCard("7. 하지 말아야 할 행동") {
        BulletList(guidance.prohibitedActions)
    }

    if (
        dangerous ||
        "REQUEST_CONSULTATION" in guidance.allowedActions
    ) {
        SectionCard("상담 요청 준비 중") {
            Text(
                "현재 상담 요청 API가 Backend Runtime에 제공되지 않아 요청을 전송할 수 없습니다.",
                fontWeight = FontWeight.Bold,
            )
            Text(
                "위험·상담 필수·근거 없음 상태에서는 해결됨 또는 문의 종료 버튼을 표시하지 않습니다.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
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
) {
    Surface(
        shape = RoundedCornerShape(28.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
        border =
            BorderStroke(
                1.dp,
                MaterialTheme.colorScheme.outline,
            ),
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .padding(18.dp),
        ) {
            Text(
                title,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.ExtraBold,
            )
            Text(
                "입력값은 유지되며 내부 오류나 Stack Trace는 표시하지 않습니다.",
            )
        }
    }

    ErrorCard(
        message,
        if (retryable) onRetry else null,
    )

    SectionCard("상담 요청 준비 중") {
        Text(
            "현재 상담 요청 API가 없어 실제 요청을 전송하지 않습니다.",
        )
    }
}
