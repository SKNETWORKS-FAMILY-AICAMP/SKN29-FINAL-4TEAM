package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassActionCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassMetricTile
import com.skn29.watercare.core.ui.components.LiquidGlassPanel
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.customer.BuildConfig
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
                WaterCareCore.customerCareRuntimeConfig,
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
        showDeveloperTools = BuildConfig.SHOW_DEVELOPER_TOOLS,
    )
}

@Composable
fun CustomerHomeContent(
    state: CustomerHomeUiState,
    onStartIntake: (subscriptionId: String) -> Unit,
    onOpenGuidance: (inquiryId: String, scenario: MockScenario) -> Unit,
    onRetry: () -> Unit,
    onLogout: () -> Unit,
    showDeveloperTools: Boolean = false,
) {
    WaterCareScreen(title = "정수기 딜러") {
        if (state.loading) {
            LoadingBlock()
        }
        state.error?.let {
            ErrorCard(it, onRetry = onRetry)
        }

        state.home?.let { home ->
            LiquidGlassPanel(strong = true) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 176.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(9.dp),
                    ) {
                        LiquidGlassPill(
                            when {
                                state.offlinePreview -> "오프라인 미리보기"
                                state.customerCareMode == CustomerCareMode.FAKE -> "Demo Mock"
                                else -> "고객용"
                            }
                        )
                        Text(
                            "${state.user?.displayName ?: "합성 고객 001"}님,\n안녕하세요",
                            style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.Black,
                        )
                        Text(
                            "우리 집 정수기를 한눈에 확인해 보세요.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Image(
                        painter = painterResource(R.drawable.mascot_customer),
                        contentDescription = "고객 안내 캐릭터",
                        modifier = Modifier.size(138.dp),
                        contentScale = ContentScale.Fit,
                    )
                }
            }

            LiquidGlassPill(state.dataSourceLabel)

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                LiquidGlassMetricTile(
                    value = home.questionnaireStatus,
                    label = "문진 상태",
                    modifier = Modifier.weight(1f),
                )
                LiquidGlassMetricTile(
                    value = home.nextCareOn,
                    label = "다음 관리",
                    modifier = Modifier.weight(1f),
                )
            }

            state.intakeUnavailableReason?.let { reason ->
                SectionCard("문의 접수 준비") {
                    Text(
                        reason,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            ProductInfoCard(
                home.product,
                home.questionnaireStatus,
                home.nextCareOn,
            )

            Text(
                "빠른 실행",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.ExtraBold,
            )
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    LiquidGlassActionCard(
                        icon = "💬",
                        title = "문진 시작",
                        subtitle = if (state.intakeAvailable) {
                            "증상을 쉽게 알려주세요"
                        } else {
                            "Demo 구독 설정이 필요해요"
                        },
                        modifier = Modifier
                            .weight(1f)
                            .heightIn(min = 142.dp)
                            .testTag("startIntake"),
                        enabled = state.intakeAvailable,
                        onClick = {
                            onStartIntake(home.subscriptionId)
                        },
                    )
                    LiquidGlassActionCard(
                        icon = "🛡",
                        title = "안심 케어",
                        subtitle = "안전 안내를 확인해요",
                        modifier = Modifier
                            .weight(1f)
                            .heightIn(min = 142.dp),
                        onClick = {
                            onOpenGuidance(
                                home.activeInquiry?.inquiryId
                                    ?: home.subscriptionId,
                                MockScenario.NORMAL,
                            )
                        },
                    )
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    LiquidGlassActionCard(
                        icon = "▦",
                        title = "QR 확인",
                        subtitle = "제품 조회 API 준비 중",
                        modifier = Modifier
                            .weight(1f)
                            .heightIn(min = 142.dp),
                        enabled = false,
                        onClick = {},
                    )
                    LiquidGlassActionCard(
                        icon = "📅",
                        title = "방문 일정",
                        subtitle = "상담사 일정 API 준비 중",
                        modifier = Modifier
                            .weight(1f)
                            .heightIn(min = 142.dp),
                        enabled = false,
                        onClick = {},
                    )
                }
            }

            home.activeInquiry?.let { active ->
                SectionCard("진행 중 문의") {
                    LiquidGlassPill(active.statusLabel)
                    Text(
                        active.inquiryCode,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    LiquidGlassButton(
                        text = "안내 다시 보기",
                        onClick = {
                            onOpenGuidance(
                                active.inquiryId,
                                MockScenario.NORMAL,
                            )
                        },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            if (showDeveloperTools) {
                SectionCard("개발 검증 도구") {
                    Text(
                        "일반·위험·근거 없음·AI 실패·네트워크 실패 화면을 재현합니다.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Column(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        MockScenario.entries.forEach { scenario ->
                            LiquidGlassButton(
                                text = when (scenario) {
                                    MockScenario.NORMAL -> "일반 안내"
                                    MockScenario.CAUTION -> "주의 안내"
                                    MockScenario.DANGER -> "위험 누수"
                                    MockScenario.NO_EVIDENCE -> "근거 없음"
                                    MockScenario.BACKEND_PROCESSING -> "Backend 처리 중"
                                    MockScenario.AI_FAILURE -> "AI 실패"
                                    MockScenario.NETWORK_FAILURE -> "네트워크 실패"
                                },
                                onClick = {
                                    onOpenGuidance(
                                        home.activeInquiry?.inquiryId
                                            ?: home.subscriptionId,
                                        scenario,
                                    )
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag("scenario_${scenario.name}"),
                            )
                        }
                    }
                }
            }

            LiquidGlassButton(
                text = "로그아웃",
                onClick = onLogout,
                enabled = !state.loggingOut,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}
