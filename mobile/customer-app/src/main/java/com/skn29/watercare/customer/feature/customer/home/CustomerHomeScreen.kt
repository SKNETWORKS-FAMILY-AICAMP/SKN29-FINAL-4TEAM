package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
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
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.ProductInfoCard
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun CustomerHomeScreen(
    offlinePreview: Boolean,
    onStartIntake: (subscriptionId: String) -> Unit,
    onOpenGuidance: (inquiryId: String, scenario: MockScenario) -> Unit,
    onLogout: () -> Unit,
) {
    val viewModel: CustomerHomeViewModel = viewModel(
        factory = VmFactory { _ ->
            CustomerHomeViewModel(
                WaterCareCore.authRepository,
                WaterCareCore.customerCareRepository,
                WaterCareCore.backendStatusRepository,
                offlinePreview,
            )
        }
    )
    val state by viewModel.state.collectAsStateWithLifecycle()

    CustomerHomeContent(
        state = state,
        onStartIntake = onStartIntake,
        onOpenGuidance = onOpenGuidance,
        onRetry = viewModel::load,
        onLogout = { viewModel.logout(onLogout) },
    )
}

@Composable
fun CustomerHomeContent(
    state: CustomerHomeUiState,
    onStartIntake: (subscriptionId: String) -> Unit,
    onOpenGuidance: (inquiryId: String, scenario: MockScenario) -> Unit,
    onRetry: () -> Unit,
    onLogout: () -> Unit,
) {
    WaterCareScreen(title = "정수기 딜러") {
        if (state.loading) LoadingBlock()
        state.error?.let { ErrorCard(it, onRetry = onRetry) }

        state.home?.let { home ->
            Surface(
                shape = RoundedCornerShape(30.dp),
                color = MaterialTheme.colorScheme.primaryContainer,
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().heightIn(min = 170.dp).padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Surface(shape = RoundedCornerShape(999.dp), color = MaterialTheme.colorScheme.tertiaryContainer) {
                            Text(
                                if (state.offlinePreview) "오프라인 미리보기" else "고객용",
                                modifier = Modifier.padding(horizontal = 11.dp, vertical = 5.dp),
                                color = MaterialTheme.colorScheme.onTertiaryContainer,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                        Text(
                            "${state.user?.displayName ?: "합성 고객 001"}님,\n안녕하세요",
                            style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.ExtraBold,
                        )
                        Text("우리 집 정수기를 한눈에 확인해 보세요.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Image(
                        painter = painterResource(R.drawable.mascot_customer),
                        contentDescription = "고객 안내 캐릭터",
                        modifier = Modifier.size(135.dp),
                        contentScale = ContentScale.Fit,
                    )
                }
            }

            AssistChip(
                onClick = {},
                label = {
                    Text(
                        if (state.backendAvailable == true) {
                            "Backend 연결됨 · 문의 생성 Remote · 홈/안내 Mock"
                        } else {
                            "Backend 미연결 · 명시적 Mock"
                        }
                    )
                },
            )

            ProductInfoCard(home.product, home.questionnaireStatus, home.nextCareOn)

            Text("빠른 메뉴", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    QuickAction(
                        icon = "💬",
                        title = "문진 시작",
                        subtitle = "증상을 쉽게 알려주세요",
                        modifier = Modifier.weight(1f).testTag("startIntake"),
                        onClick = { onStartIntake(home.subscriptionId) },
                    )
                    QuickAction(
                        icon = "🛡",
                        title = "안심 케어",
                        subtitle = "안전 안내를 확인해요",
                        modifier = Modifier.weight(1f),
                        onClick = {
                            onOpenGuidance(
                                home.activeInquiry?.inquiryId ?: home.subscriptionId,
                                MockScenario.NORMAL,
                            )
                        },
                    )
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    UnavailableAction("▦", "QR 확인", "제품 조회 API 준비 중", Modifier.weight(1f))
                    UnavailableAction("📅", "방문 일정", "상담사 일정 API 준비 중", Modifier.weight(1f))
                }
            }

            home.activeInquiry?.let { active ->
                SectionCard("진행 중 문의") {
                    Text(active.inquiryCode, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
                    Text(active.statusLabel)
                    OutlinedButton(
                        onClick = { onOpenGuidance(active.inquiryId, MockScenario.NORMAL) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("안내 다시 보기") }
                }
            }

            SectionCard("개발 검증 도구") {
                Text(
                    "일반·위험·근거 없음·AI 실패·네트워크 실패 화면을 재현합니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    MockScenario.entries.forEach { scenario ->
                        OutlinedButton(
                            onClick = {
                                onOpenGuidance(
                                    home.activeInquiry?.inquiryId ?: home.subscriptionId,
                                    scenario,
                                )
                            },
                            modifier = Modifier.fillMaxWidth().testTag("scenario_${scenario.name}"),
                        ) {
                            Text(
                                when (scenario) {
                                    MockScenario.NORMAL -> "일반 안내"
                                    MockScenario.CAUTION -> "주의 안내"
                                    MockScenario.DANGER -> "위험 누수"
                                    MockScenario.NO_EVIDENCE -> "근거 없음"
                                    MockScenario.BACKEND_PROCESSING -> "Backend 처리 중"
                                    MockScenario.AI_FAILURE -> "AI 실패"
                                    MockScenario.NETWORK_FAILURE -> "네트워크 실패"
                                }
                            )
                        }
                    }
                }
            }

            TextButton(
                onClick = onLogout,
                enabled = !state.loggingOut,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("로그아웃") }
        }
    }
}

@Composable
private fun QuickAction(
    icon: String,
    title: String,
    subtitle: String,
    modifier: Modifier,
    onClick: () -> Unit,
) {
    Card(
        onClick = onClick,
        modifier = modifier.height(140.dp),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(
            Modifier.fillMaxSize().padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(icon, style = MaterialTheme.typography.headlineSmall)
            Text(title, fontWeight = FontWeight.ExtraBold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun UnavailableAction(
    icon: String,
    title: String,
    subtitle: String,
    modifier: Modifier,
) {
    Card(
        modifier = modifier.height(140.dp),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(
            Modifier.fillMaxSize().padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(icon, style = MaterialTheme.typography.headlineSmall)
            Text(title, fontWeight = FontWeight.ExtraBold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
