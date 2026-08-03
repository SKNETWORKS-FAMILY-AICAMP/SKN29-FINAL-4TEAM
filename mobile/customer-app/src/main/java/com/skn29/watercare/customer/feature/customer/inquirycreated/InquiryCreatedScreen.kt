package com.skn29.watercare.customer.feature.customer.inquirycreated

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.customer.CustomerRuntime
import com.skn29.watercare.core.model.InquiryDisplayState
import com.skn29.watercare.core.model.InquiryStatusMapper
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun InquiryCreatedScreen(
    inquiryId: String,
    previewScenario: MockScenario,
    onBack: () -> Unit,
    onOpenMockGuidance: (String, MockScenario) -> Unit,
    onDone: () -> Unit,
) {
    val viewModel: InquiryCreatedViewModel = viewModel(
        factory = VmFactory {
            InquiryCreatedViewModel(
                inquiryId = inquiryId,
                repository = CustomerRuntime.inquiryRepository,
                sessionStore = CustomerRuntime.inquirySessionStore,
            )
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()
    var showCancelConfirm by remember { mutableStateOf(false) }

    if (showCancelConfirm) {
        AlertDialog(
            onDismissRequest = { showCancelConfirm = false },
            title = { Text("문의를 취소하시겠습니까?") },
            text = { Text("Backend의 CANCEL_INQUIRY Endpoint를 실제 호출합니다.") },
            confirmButton = {
                TextButton(onClick = {
                    showCancelConfirm = false
                    viewModel.cancel()
                }) { Text("취소 진행") }
            },
            dismissButton = {
                TextButton(onClick = { showCancelConfirm = false }) { Text("돌아가기") }
            },
        )
    }

    WaterCareScreen(title = "문의 접수 결과", onBack = onBack) {
        if (state.loading) {
            LoadingBlock("Backend 문의 결과를 확인하고 있습니다")
            return@WaterCareScreen
        }

        state.error?.let {
            ErrorCard(it, onRetry = if (state.retryable) viewModel::cancel else null)
        }

        state.inquiry?.let { inquiry ->
            val cancelled = inquiry.displayState == InquiryDisplayState.CANCELLED
            Surface(
                shape = RoundedCornerShape(28.dp),
                color = if (cancelled) {
                    MaterialTheme.colorScheme.surfaceVariant
                } else {
                    MaterialTheme.colorScheme.primaryContainer
                },
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    AssistChip(
                        onClick = {},
                        label = { Text(if (cancelled) "실제 Backend 취소 완료" else "실제 Backend 접수 완료") },
                    )
                    Text(
                        inquiry.inquiryCode.ifBlank { inquiry.inquiryId },
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    Text("상태 · ${InquiryStatusMapper.label(inquiry.serverStatus)}")
                    Text("state_version · ${inquiry.stateVersion}")
                    if (inquiry.idempotentReplay) {
                        Text("동일 Idempotency-Key 재요청 결과가 재사용되었습니다.")
                    }
                }
            }

            SectionCard("Backend allowed_actions") {
                if (inquiry.allowedActions.isEmpty()) {
                    Text("현재 Backend가 허용한 후속 행동이 없습니다.")
                } else {
                    inquiry.allowedActions.forEach { action ->
                        if (action.objectContractAvailable) {
                            Text("• ${action.label} (${action.code})")
                        } else {
                            Text("• 코드만 수신됨: ${action.code}")
                        }
                    }
                    if (inquiry.allowedActions.any { !it.objectContractAvailable }) {
                        Text(
                            "완전한 행동 객체를 받기 전까지 상태 변경 버튼은 안전을 위해 비활성화됩니다.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
                Text(
                    "Mobile은 상태를 보고 행동을 임의 생성하지 않고 Backend 응답만 사용합니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            state.correlationId?.let { correlationId ->
                SectionCard("요청 추적 정보") {
                    Text("correlation_id · $correlationId", style = MaterialTheme.typography.bodySmall)
                }
            }

            if (!cancelled && inquiry.allowedActions.any {
                    it.code == "CANCEL_INQUIRY" && it.objectContractAvailable
                }) {
                Button(
                    onClick = { showCancelConfirm = true },
                    enabled = !state.cancelling,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                ) {
                    Text(if (state.cancelling) "취소 처리 중" else "실제 문의 취소")
                }
            }

            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                shape = RoundedCornerShape(22.dp),
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text("다음 화면은 Mock/Blocked", fontWeight = FontWeight.ExtraBold)
                    Text("추가 문진·Guidance·상담·문의 상세 API는 Backend Runtime 제공 전까지 실제 호출하지 않습니다.")
                    OutlinedButton(
                        onClick = { onOpenMockGuidance(inquiry.inquiryId, previewScenario) },
                        enabled = !cancelled,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Mock Guidance 미리보기")
                    }
                }
            }

            OutlinedButton(onClick = onDone, modifier = Modifier.fillMaxWidth()) {
                Text("홈으로")
            }
        }
    }
}
