package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.ReferenceActionItem
import com.skn29.watercare.core.ui.components.ReferenceActionRow
import com.skn29.watercare.core.ui.components.ReferenceBottomItem
import com.skn29.watercare.core.ui.components.ReferenceCompactBanner
import com.skn29.watercare.core.ui.components.ReferenceDashboardScaffold
import com.skn29.watercare.core.ui.components.ReferenceDetailCard
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceGlassPanel
import com.skn29.watercare.core.ui.components.ReferenceHeroCard
import com.skn29.watercare.core.ui.components.ReferenceSectionHeader
import com.skn29.watercare.core.ui.components.ReferenceStatusItem
import com.skn29.watercare.core.ui.components.ReferenceStatusRow
import com.skn29.watercare.customer.BuildConfig
import com.skn29.watercare.customer.R
import com.skn29.watercare.customer.common.VmFactory

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
    val palette = CustomerReferencePalette

    ReferenceDashboardScaffold(
        title = "정수기 딜러",
        roleLabel = "고객용",
        palette = palette,
        backgroundRes = R.drawable.water_background_customer,
        bottomItems = listOf(
            ReferenceBottomItem(
                iconRes = R.drawable.ref_home,
                label = "홈",
                selected = true,
            ),
            ReferenceBottomItem(
                iconRes = R.drawable.ref_product,
                label = "제품",
                enabled = false,
            ),
            ReferenceBottomItem(
                iconRes = R.drawable.ref_manage,
                label = "관리",
                enabled = false,
            ),
            ReferenceBottomItem(
                iconRes = R.drawable.ref_notice,
                label = "알림",
                enabled = false,
            ),
            ReferenceBottomItem(
                iconRes = R.drawable.ref_profile,
                label = "마이",
                enabled = false,
            ),
        ),
    ) {
        if (state.loading) {
            LoadingBlock()
        }

        state.error?.let {
            ErrorCard(it, onRetry = onRetry)
        }

        state.home?.let { home ->
            val displayName = state.user?.displayName
                ?.takeIf(String::isNotBlank)
                ?.removeSuffix("님")
                ?: "합성 고객 001"
            val activeInquiry = home.activeInquiry
            val previewLabel = when {
                state.offlinePreview ->
                    "오프라인 UI 미리보기"
                state.customerCareMode == CustomerCareMode.FAKE ->
                    "Demo Mock"
                else ->
                    "계측 API 연결 전 UI 예시"
            }

            ReferenceHeroCard(
                greeting = "${displayName}님,\n안녕하세요",
                subtitle = "깨끗한 물로 건강한 하루 되세요.",
                metricLabel = "오늘의 사용량",
                metricValue = "12.5",
                metricUnit = "L / 20L",
                progress = 0.62f,
                footnote = previewLabel,
                imageRes = R.drawable.mascot_customer,
                palette = palette,
            )

            ReferenceSectionHeader(
                title = "홈 상태",
                trailing = "현재 제공 데이터 기준",
                palette = palette,
            )
            ReferenceStatusRow(
                items = listOf(
                    ReferenceStatusItem(
                        iconRes = R.drawable.ref_filter,
                        label = "문진 상태",
                        value = home.questionnaireStatus,
                    ),
                    ReferenceStatusItem(
                        iconRes = R.drawable.ref_temperature,
                        label = "다음 관리",
                        value = home.nextCareOn,
                    ),
                    ReferenceStatusItem(
                        iconRes = R.drawable.ref_dispense,
                        label = "제품 상태",
                        value = "확인 완료",
                    ),
                    ReferenceStatusItem(
                        iconRes = R.drawable.ref_power,
                        label = "진행 문의",
                        value = activeInquiry?.statusLabel ?: "없음",
                    ),
                ),
                palette = palette,
            )

            state.intakeUnavailableReason?.let { reason ->
                ReferenceCompactBanner(
                    title = "문의 접수 준비",
                    message = reason,
                    palette = palette,
                    warning = true,
                )
            }

            ReferenceSectionHeader(
                title = "빠른 실행",
                trailing = "자주 사용하는 기능",
                palette = palette,
            )
            ReferenceActionRow(
                items = listOf(
                    ReferenceActionItem(
                        iconRes = R.drawable.ref_intake,
                        label = "문진 시작",
                        subtitle = if (state.intakeAvailable) {
                            "증상 입력"
                        } else {
                            "설정 필요"
                        },
                        enabled = state.intakeAvailable,
                        testTag = "startIntake",
                        onClick = {
                            onStartIntake(home.subscriptionId)
                        },
                    ),
                    ReferenceActionItem(
                        iconRes = R.drawable.ref_care,
                        label = "안내 미리보기",
                        subtitle = "Fixture 안내",
                        onClick = {
                            onOpenGuidance(
                                activeInquiry?.inquiryId
                                    ?: home.subscriptionId,
                                MockScenario.NORMAL,
                            )
                        },
                    ),
                    ReferenceActionItem(
                        iconRes = R.drawable.ref_schedule,
                        label = "방문 일정",
                        subtitle = "API 준비 중",
                        enabled = false,
                        onClick = {},
                    ),
                    ReferenceActionItem(
                        iconRes = R.drawable.ref_product,
                        label = "제품 정보",
                        subtitle = "준비 중",
                        enabled = false,
                        onClick = {},
                    ),
                ),
                palette = palette,
            )

            ReferenceSectionHeader(
                title = "사용 중인 제품",
                palette = palette,
            )
            ReferenceDetailCard(
                imageRes = R.drawable.dashboard_purifier,
                title = home.product.modelName,
                badge = home.product.managementTypeLabel,
                lines = listOf(
                    "모델명  ${home.product.modelCode}",
                    "식별번호  ${home.product.serialNo}",
                    "다음 관리  ${home.nextCareOn}",
                ),
                status = "현재 정보 확인 완료",
                palette = palette,
                primaryActionLabel = "제품 상세 · 준비 중",
                secondaryActionLabel = "관리 가이드 · 준비 중",
                onPrimaryAction = {},
                onSecondaryAction = {},
                primaryActionEnabled = false,
                secondaryActionEnabled = false,
            )

            ReferenceSectionHeader(
                title = "서비스 & 지원",
                trailing = "더보기 ›",
                palette = palette,
            )
            ReferenceActionRow(
                items = listOf(
                    ReferenceActionItem(
                        iconRes = R.drawable.ref_support,
                        label = "고객센터",
                        subtitle = "준비 중",
                        enabled = false,
                        onClick = {},
                    ),
                    ReferenceActionItem(
                        iconRes = R.drawable.ref_selfcheck,
                        label = "자가 점검",
                        subtitle = "준비 중",
                        enabled = false,
                        onClick = {},
                    ),
                    ReferenceActionItem(
                        iconRes = R.drawable.ref_benefit,
                        label = "보증/혜택",
                        subtitle = "준비 중",
                        enabled = false,
                        onClick = {},
                    ),
                    ReferenceActionItem(
                        iconRes = R.drawable.ref_event,
                        label = "이벤트",
                        subtitle = "준비 중",
                        enabled = false,
                        onClick = {},
                    ),
                ),
                palette = palette,
            )

            activeInquiry?.let { active ->
                ReferenceGlassPanel(
                    palette = palette,
                    strong = true,
                ) {
                    Text(
                        "진행 중 문의",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Black,
                    )
                    Text(
                        active.inquiryCode,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    Text(
                        active.statusLabel,
                        color = palette.accent,
                    )
                    ReferenceGlassButton(
                        text = "안내 미리보기",
                        palette = palette,
                        accent = true,
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
                ReferenceGlassPanel(palette = palette) {
                    Text(
                        "개발 검증 도구",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Black,
                    )
                    Column(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        MockScenario.entries.forEach { scenario ->
                            ReferenceGlassButton(
                                text = scenarioLabel(scenario),
                                palette = palette,
                                onClick = {
                                    onOpenGuidance(
                                        activeInquiry?.inquiryId
                                            ?: home.subscriptionId,
                                        scenario,
                                    )
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag(
                                        "scenario_${scenario.name}"
                                    ),
                            )
                        }
                    }
                }
            }

            ReferenceGlassButton(
                text = "로그아웃",
                palette = palette,
                onClick = onLogout,
                enabled = !state.loggingOut,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

private fun scenarioLabel(
    scenario: MockScenario,
): String = when (scenario) {
    MockScenario.NORMAL -> "일반 안내"
    MockScenario.CAUTION -> "주의 안내"
    MockScenario.DANGER -> "위험 누수"
    MockScenario.NO_EVIDENCE -> "근거 없음"
    MockScenario.BACKEND_PROCESSING -> "Backend 처리 중"
    MockScenario.AI_FAILURE -> "AI 실패"
    MockScenario.NETWORK_FAILURE -> "네트워크 실패"
}
