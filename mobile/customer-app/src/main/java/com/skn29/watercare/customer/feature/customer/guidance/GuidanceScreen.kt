package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.GuidanceDisplayModel
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.InquiryLabels
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.RiskLevel
import com.skn29.watercare.core.model.UsageGuidanceStatus
import com.skn29.watercare.core.repository.FakeCustomerCareRepository
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPanel
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.BulletList
import com.skn29.watercare.customer.feature.shared.EvidenceCard
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.StatusBadge
import com.skn29.watercare.customer.feature.shared.WaterCareScreen
import com.skn29.watercare.customer.feature.shared.WorkflowActionButton

@Composable
fun GuidanceScreen(
    inquiryId: String,
    scenario: MockScenario,
    submittedInquiryCode: String = "",
    submittedStatusCode: String? = null,
    submittedStateVersion: Int? = null,
    submittedAllowedActions: List<AllowedAction> = emptyList(),
    submittedIdempotentReplay: Boolean? = null,
    fixturePreview: Boolean = false,
    onBack: () -> Unit,
    onDone: () -> Unit,
) {
    val guidanceRepository = if (fixturePreview) {
        FakeCustomerCareRepository(
            fixtureSubscriptionId =
                WaterCareCore.customerCareRuntimeConfig.fixtureSubscriptionId,
        )
    } else {
        WaterCareCore.customerCareRepository
    }

    val viewModel: GuidanceViewModel = viewModel(
        factory = VmFactory { _ ->
            GuidanceViewModel(
                inquiryId,
                scenario,
                guidanceRepository,
            )
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()
    var consultationNotice by remember { mutableStateOf(false) }
    val requestConsultation = {
        consultationNotice = true
    }
    val actualInquiryCode = submittedInquiryCode.trim()

    WaterCareScreen(title = "AI 자가진단", onBack = onBack) {
        if (fixturePreview) {
            SectionCard("합성 Fixture 미리보기") {
                Text(
                    "이 화면의 안내는 UI 검증용 합성 데이터이며 실제 Backend·AI 결과가 아닙니다."
                )
            }
        }

        if (actualInquiryCode.isNotEmpty()) {
            SubmissionReceiptCard(
                inquiryCode = actualInquiryCode,
                statusCode = submittedStatusCode,
                stateVersion = submittedStateVersion,
                allowedActions = submittedAllowedActions,
                idempotentReplay = submittedIdempotentReplay,
            )
        }

        when (val current = state) {
            GuidanceUiState.Loading ->
                LoadingBlock("AI 안내 결과를 불러오는 중입니다")

            is GuidanceUiState.Content -> GuidanceContent(
                guidance = current.guidance.withInquiryCode(
                    actualInquiryCode
                ),
                noEvidence = false,
                onRetry = viewModel::load,
                onRequestConsultation = requestConsultation,
            )

            is GuidanceUiState.NoEvidence -> GuidanceContent(
                guidance = current.guidance.withInquiryCode(
                    actualInquiryCode
                ),
                noEvidence = true,
                onRetry = viewModel::load,
                onRequestConsultation = requestConsultation,
            )

            is GuidanceUiState.AiFailure -> FailureFallback(
                title = "AI 안내 생성 실패",
                message = current.message,
                retryable = current.retryable,
                onRetry = viewModel::load,
            )

            is GuidanceUiState.NetworkFailure -> FailureFallback(
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

        if (consultationNotice) {
            SectionCard("상담 요청") {
                Text(
                    "상담 요청 API가 아직 제공되지 않아 실제 요청을 보내지 않았습니다."
                )
            }
        }
    }
}

private fun GuidanceDisplayModel.withInquiryCode(
    submittedInquiryCode: String,
): GuidanceDisplayModel =
    submittedInquiryCode.takeIf(String::isNotEmpty)
        ?.let { copy(inquiryCode = it) }
        ?: this

@Composable
private fun SubmissionReceiptCard(
    inquiryCode: String,
    statusCode: String?,
    stateVersion: Int?,
    allowedActions: List<AllowedAction>,
    idempotentReplay: Boolean?,
) {
    LiquidGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("submissionReceipt"),
        strong = true,
    ) {
        LiquidGlassPill("문의 접수 완료")
        Text(
            inquiryCode,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Black,
        )

        statusCode
            ?.trim()
            ?.uppercase()
            ?.takeIf(String::isNotEmpty)
            ?.let { code ->
                Text(
                    "현재 상태 · ${InquiryLabels.status(code)} ($code)"
                )
            }

        stateVersion?.let { version ->
            Text("상태 버전 · $version")
        }

        if (allowedActions.isNotEmpty()) {
            Text(
                "Backend 허용 행동",
                fontWeight = FontWeight.Bold,
            )
            allowedActions.forEach { action ->
                Text("• ${action.displayLabel}")
            }
        } else {
            Text(
                "현재 화면에서 실행할 수 있는 Backend 허용 행동이 없습니다.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (idempotentReplay == true) {
            Text(
                "동일 요청이 재전송되어 기존 접수 결과를 안전하게 재사용했습니다.",
                style = MaterialTheme.typography.bodySmall,
            )
        }

        Text(
            "데이터 출처 · 문의 생성·증상 제출 실제 API 응답",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
fun GuidanceContent(
    guidance: GuidanceDisplayModel,
    noEvidence: Boolean,
    onRetry: () -> Unit,
    onRequestConsultation: () -> Unit,
) {
    val dangerous = guidance.requiresConsultation ||
        guidance.riskLevel == RiskLevel.DANGER ||
        guidance.usageStatus == UsageGuidanceStatus.TOTAL_STOP ||
        guidance.usageStatus ==
            UsageGuidanceStatus.PENDING_CONSULTATION ||
        noEvidence

    LiquidGlassPanel(
        strong = !dangerous,
        danger = dangerous,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 165.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
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
                    fontWeight = FontWeight.Black,
                )
                Text(
                    "문의번호 ${guidance.inquiryCode}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Image(
                painter = painterResource(R.drawable.mascot_customer),
                contentDescription = "안전 안내 캐릭터",
                modifier = Modifier.size(125.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }

    SectionCard(
        "1. 지금 해야 할 행동",
        isDanger = dangerous,
    ) {
        Text(
            guidance.nextAction,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.ExtraBold,
        )
    }

    SectionCard(
        "2. 사용 가능 여부",
        isDanger = dangerous,
    ) {
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

    SectionCard(
        "3. 안전 행동",
        isDanger = dangerous,
    ) {
        BulletList(
            guidance.safeActions,
            emptyText = if (noEvidence) {
                "근거가 없어 자가조치를 추정하지 않습니다."
            } else {
                "추가 안전조치가 없습니다."
            },
        )
    }

    SectionCard(
        "4. 상담이 필요한 경우",
        isDanger = dangerous,
    ) {
        BulletList(guidance.escalationConditions)
    }

    SectionCard("5. 공식 근거") {
        if (guidance.evidence.isEmpty()) {
            Text(
                "표시 가능한 공식 근거가 없습니다. 판단을 보류하고 상담 확인을 우선합니다."
            )
            LiquidGlassButton(
                text = "근거 다시 확인",
                onClick = onRetry,
                accent = true,
                modifier = Modifier.fillMaxWidth(),
            )
        } else {
            guidance.evidence.forEach {
                EvidenceCard(it)
            }
        }
    }

    SectionCard("6. 입력한 증상 요약") {
        Text(guidance.symptomSummary)
    }

    SectionCard(
        "7. 하지 말아야 할 행동",
        isDanger = dangerous,
    ) {
        BulletList(guidance.prohibitedActions)
    }

    val consultationAction = guidance.allowedActions.firstOrNull {
        it.normalizedCode ==
            InquiryActionLabels.REQUEST_CONSULTATION
    }

    if (consultationAction != null) {
        LiquidGlassButton(
            text = "상담 요청 · API 준비 중",
            onClick = {},
            enabled = false,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("consultationUnavailable"),
        )
    } else if (dangerous) {
        LiquidGlassButton(
            text = "상담 요청 준비 중",
            onClick = {},
            enabled = false,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("consultationUnavailable"),
        )
    }

    if (dangerous) {
        Text(
            "위험·상담 필수·근거 없음 상태에서는 해결됨 또는 문의 종료 버튼을 표시하지 않습니다.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun FailureFallback(
    title: String,
    message: String,
    retryable: Boolean,
    onRetry: () -> Unit,
) {
    LiquidGlassPanel(strong = true) {
        Text(
            title,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Black,
        )
        Text(
            "입력값은 유지되며 내부 오류나 Stack Trace는 표시하지 않습니다."
        )
    }

    ErrorCard(
        message,
        if (retryable) onRetry else null,
    )

    LiquidGlassButton(
        text = "상담 요청 준비 중",
        onClick = {},
        enabled = false,
        modifier = Modifier.fillMaxWidth(),
    )
}
