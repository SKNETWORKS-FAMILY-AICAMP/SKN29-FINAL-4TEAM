package com.skn29.watercare.technician

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
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
import com.skn29.watercare.core.ui.components.ReferenceWelcomeCard
import com.skn29.watercare.core.ui.components.TechnicianReferencePalette

@Composable
fun TechnicianReferenceLogin(
    state: TechnicianUiState,
    onLogin: () -> Unit,
    onOfflinePreview: () -> Unit,
    onRetryBackend: () -> Unit,
) {
    val palette = TechnicianReferencePalette

    ReferenceDashboardScaffold(
        title = "정수기 딜러",
        roleLabel = "방문기사용",
        palette = palette,
        backgroundRes = R.drawable.water_splash_technician_r19,
    ) {
        ReferenceWelcomeCard(
            title = "방문 업무를\n시작하세요",
            subtitle = "배정 방문과 읽기 전용 사전 점검 내용을 확인합니다.",
            imageRes = R.drawable.dashboard_toolkit,
            palette = palette,
        )

        when {
            state.checkingBackend -> {
                ReferenceCompactBanner(
                    title = "Backend 확인 중",
                    message = "Demo 로그인 가능 여부를 확인하고 있습니다.",
                    palette = palette,
                )
            }

            state.backendAvailable == true -> {
                ReferenceCompactBanner(
                    title = "Backend 연결됨",
                    message = "실제 Demo 인증으로 로그인할 수 있습니다.",
                    palette = palette,
                )
            }

            else -> {
                ReferenceCompactBanner(
                    title = "Backend 연결 확인 필요",
                    message = "방문 대시보드는 합성 Fixture 미리보기로 확인할 수 있습니다.",
                    palette = palette,
                    warning = true,
                    actionLabel = "다시 확인",
                    onAction = onRetryBackend,
                )
            }
        }

        ReferenceGlassButton(
            text = "방문기사 Demo 로그인",
            palette = palette,
            onClick = onLogin,
            enabled = !state.loginLoading &&
                !state.restoringSession &&
                state.backendAvailable == true,
            accent = true,
            modifier = Modifier.fillMaxWidth(),
        )
        ReferenceGlassButton(
            text = "합성 방문 대시보드 미리보기",
            palette = palette,
            onClick = onOfflinePreview,
            enabled = !state.loginLoading &&
                !state.restoringSession,
            accent = false,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("technicianOfflinePreview"),
        )

        if (state.restoringSession) {
            LoadingBlock(
                "저장된 방문기사 세션을 확인하는 중입니다"
            )
        }
        if (state.loginLoading) {
            LoadingBlock(
                "방문기사 계정을 확인하는 중입니다"
            )
        }
        state.error?.let {
            ErrorCard(it, onRetry = onLogin)
        }

        Text(
            "방문 목록과 사전 점검은 방문 API가 제공되기 전까지 합성 Fixture입니다.",
            style = MaterialTheme.typography.bodySmall,
            color = palette.textMuted,
        )
    }
}

@Composable
fun TechnicianReferenceDashboard(
    state: TechnicianUiState,
    onVisitClick: (String) -> Unit,
    onRefresh: () -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val palette = TechnicianReferencePalette
    val total = state.visits.size
    val confirmed = state.visits.count {
        it.scheduleStatusCode == "CONFIRMED"
    }
    val risky = state.visits.count {
        it.risk == TechnicianVisitRisk.CAUTION ||
            it.risk == TechnicianVisitRisk.DANGER
    }
    val dangerCount = state.visits.count {
        it.risk == TechnicianVisitRisk.DANGER
    }
    val progress = if (total == 0) {
        0f
    } else {
        confirmed.toFloat() / total.toFloat()
    }
    val primaryVisit = state.visits.firstOrNull()
    val displayName = state.user?.displayName
        ?.takeIf(String::isNotBlank)
        ?.removeSuffix("님")
        ?: "방문기사"

    ReferenceDashboardScaffold(
        title = "정수기 딜러",
        roleLabel = "방문기사용",
        palette = palette,
        backgroundRes = R.drawable.water_splash_technician_r19,
        modifier = modifier,
        bottomItems = listOf(
    ReferenceBottomItem(
        iconRes = R.drawable.ref_home,
        label = "홈",
        selected = true,
    ),
    ReferenceBottomItem(
        iconRes = R.drawable.ref_schedule,
        label = "방문",
    ),
    ReferenceBottomItem(
        iconRes = R.drawable.ref_work,
        label = "작업",
    ),
    ReferenceBottomItem(
        iconRes = R.drawable.ref_profile,
        label = "마이",
    ),
),
    ) {
        ReferenceHeroCard(
            greeting = if (
                displayName.contains("합성", ignoreCase = true) ||
                displayName.contains("SYN", ignoreCase = true)
            ) {
                "기사님,\n안녕하세요"
            } else {
                "${displayName}님,\n안녕하세요"
            },
            subtitle = "오늘 방문 일정을 빠르게 확인해보세요.",
            metricLabel = "",
            metricValue = "",
            metricUnit = "",
            progress = 0f,
            footnote = "",
            imageRes = R.drawable.dashboard_toolkit,
            palette = palette,
            roleLabel = "방문기사용",
            imageEmphasis = 1.04f,
        )

        ReferenceSectionHeader(
            title = "오늘 일정",
            trailing = "방문 현황",
            palette = palette,
        )
        ReferenceStatusRow(
            items = listOf(
                ReferenceStatusItem(
                    iconRes = R.drawable.ref_schedule,
                    label = "오늘 방문",
                    value = "${total}건",
                ),
                ReferenceStatusItem(
                    iconRes = R.drawable.ref_complete,
                    label = "확정 일정",
                    value = "${confirmed}건",
                ),
                ReferenceStatusItem(
                    iconRes = R.drawable.ref_urgent,
                    label = "긴급 요청",
                    value = "${dangerCount}건",
                    healthy = dangerCount == 0,
                ),
            ),
            palette = palette,
        )

        ReferenceSectionHeader(
            title = "빠른 실행",
            trailing = "전체보기 ›",
            palette = palette,
        )
        ReferenceActionRow(
            items = listOf(
                ReferenceActionItem(
                    iconRes = R.drawable.ref_visits,
                    label = "방문 목록",
                    subtitle = "${total}건",
                    onClick = onRefresh,
                ),
                ReferenceActionItem(
                    iconRes = R.drawable.ref_precheck,
                    label = "사전 점검",
                    subtitle = "읽기 전용",
                    onClick = {
                        primaryVisit?.let {
                            onVisitClick(it.visitId)
                        }
                    },
                ),
                ReferenceActionItem(
                    iconRes = R.drawable.ref_route,
                    label = "경로 확인",
                    subtitle = "개인 확장",
                    enabled = false,
                    onClick = {},
                ),
                ReferenceActionItem(
                    iconRes = R.drawable.ref_report,
                    label = "작업 기록",
                    subtitle = "API 준비 중",
                    enabled = false,
                    onClick = {},
                ),
            ),
            palette = palette,
        )

        if (state.visitsLoading) {
            LoadingBlock(
                "배정 방문 목록을 불러오는 중입니다"
            )
        }

        state.error?.let {
            ErrorCard(it, onRetry = onRefresh)
        }

        ReferenceSectionHeader(
            title = "오늘의 작업",
            palette = palette,
        )

        if (primaryVisit == null) {
            ReferenceGlassPanel(palette = palette) {
                Text(
                    "현재 배정된 방문이 없습니다.",
                    color = palette.textMuted,
                )
            }
        } else {
            ReferenceDetailCard(
                imageRes = R.drawable.dashboard_toolkit,
                title = primaryVisit.customerMaskedName,
                badge = primaryVisit.scheduleStatusLabel,
                lines = listOf(
                    "제품  ${primaryVisit.productModel}",
                    "주소  ${primaryVisit.maskedAddress}",
                    "시간  ${primaryVisit.scheduledAt}",
                ),
                status = primaryVisit.usageRestrictionLabel,
                palette = palette,
                primaryActionLabel = "방문 상세",
                secondaryActionLabel = "새로고침",
                onPrimaryAction = {
                    onVisitClick(primaryVisit.visitId)
                },
                onSecondaryAction = onRefresh,
                timeline = listOf(
                    "배정",
                    "방문 예정",
                    "점검",
                    "완료",
                ),
                selectedTimelineIndex = if (
                    primaryVisit.scheduleStatusCode == "CONFIRMED"
                ) {
                    1
                } else {
                    0
                },
            )
        }

        ReferenceCompactBanner(
            title = if (state.offlinePreview) {
                "오프라인 합성 데이터"
            } else {
                "방문 API 연결 대기"
            },
            message = if (state.offlinePreview) {
                "방문 API 연결 전까지 사용자가 선택한 샘플 데이터를 표시합니다."
            } else {
                "실제 Visit Runtime이 제공되면 Remote 데이터로 전환합니다."
            },
            palette = palette,
            warning = !state.offlinePreview,
        )

        ReferenceSectionHeader(
            title = "업무 도구",
            trailing = "더보기 ›",
            palette = palette,
        )
        ReferenceActionRow(
            items = listOf(
                ReferenceActionItem(
                    iconRes = R.drawable.ref_support,
                    label = "고객센터",
                    subtitle = "1:1 문의",
                    onClick = {},
                ),
                ReferenceActionItem(
                    iconRes = R.drawable.ref_parts,
                    label = "부품 확인",
                    subtitle = "API 준비 중",
                    enabled = false,
                    onClick = {},
                ),
                ReferenceActionItem(
                    iconRes = R.drawable.ref_safety,
                    label = "안전 체크",
                    subtitle = "점검 항목",
                    onClick = {
                        primaryVisit?.let {
                            onVisitClick(it.visitId)
                        }
                    },
                ),
                ReferenceActionItem(
                    iconRes = R.drawable.ref_report,
                    label = "리포트",
                    subtitle = "읽기 전용",
                    onClick = {
                        primaryVisit?.let {
                            onVisitClick(it.visitId)
                        }
                    },
                ),
            ),
            palette = palette,
        )

        ReferenceGlassButton(
            text = "로그아웃",
            palette = palette,
            onClick = onLogout,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}
