package com.skn29.watercare.technician

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.ReferenceActionItem
import com.skn29.watercare.core.ui.components.ReferenceActionRow
import com.skn29.watercare.core.ui.components.ReferenceBottomItem
import com.skn29.watercare.core.ui.components.ReferenceBottomNavigation
import com.skn29.watercare.core.ui.components.ReferenceDashboardHeader
import com.skn29.watercare.core.ui.components.ReferenceDetailCard
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceGlassPanel
import com.skn29.watercare.core.ui.components.ReferenceHeroCard
import com.skn29.watercare.core.ui.components.ReferenceSectionHeader
import com.skn29.watercare.core.ui.components.ReferenceStatusItem
import com.skn29.watercare.core.ui.components.ReferenceStatusRow
import com.skn29.watercare.core.ui.components.TechnicianReferencePalette

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
    val progress = if (total == 0) {
        0f
    } else {
        confirmed.toFloat() / total.toFloat()
    }
    val primaryVisit = state.visits.firstOrNull()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        ReferenceDashboardHeader(
            roleLabel = "방문기사용",
            palette = palette,
        )

        ReferenceHeroCard(
            greeting = "${state.user?.displayName.orEmpty()} 기사님, 안녕하세요!",
            subtitle = "안전하고 정확한 방문 서비스를 응원합니다.",
            metricLabel = "오늘 방문",
            metricValue = "$total",
            metricUnit = "건",
            progress = progress,
            footnote = "진행 $confirmed 건 · ${(progress * 100).toInt()}%",
            imageRes = R.drawable.dashboard_toolkit,
            palette = palette,
        )

        ReferenceGlassPanel(
            palette = palette,
        ) {
            Text(
                if (state.offlinePreview) {
                    "오프라인 합성 Fixture"
                } else {
                    "Demo 인증 + 합성 방문 Fixture"
                },
                color = palette.accent,
                fontWeight = FontWeight.ExtraBold,
            )
            Text(
                "방문 API가 제공되기 전까지 합성 방문 데이터를 표시합니다.",
                color = palette.textMuted,
                style = MaterialTheme.typography.bodySmall,
            )
        }

        ReferenceSectionHeader(
            title = "방문 상태",
            trailing = "현재 목록 기준",
            palette = palette,
        )
        ReferenceStatusRow(
            items = listOf(
                ReferenceStatusItem(
                    icon = "▦",
                    label = "오늘 일정",
                    value = "${total}건",
                ),
                ReferenceStatusItem(
                    icon = "✓",
                    label = "확정",
                    value = "${confirmed}건",
                ),
                ReferenceStatusItem(
                    icon = "⌖",
                    label = "점검 필요",
                    value = "${risky}건",
                    healthy = risky == 0,
                ),
                ReferenceStatusItem(
                    icon = "!",
                    label = "긴급",
                    value = state.visits.count {
                        it.risk == TechnicianVisitRisk.DANGER
                    }.let { "${it}건" },
                    healthy = state.visits.none {
                        it.risk == TechnicianVisitRisk.DANGER
                    },
                ),
            ),
            palette = palette,
        )

        ReferenceSectionHeader(
            title = "빠른 실행",
            trailing = "자주 사용하는 기능",
            palette = palette,
        )
        ReferenceActionRow(
            items = listOf(
                ReferenceActionItem(
                    icon = "▤",
                    label = "방문 목록",
                    subtitle = "${total}건",
                    onClick = onRefresh,
                ),
                ReferenceActionItem(
                    icon = "🔧",
                    label = "사전 점검",
                    subtitle = "읽기 전용",
                    onClick = {
                        primaryVisit?.let {
                            onVisitClick(it.visitId)
                        }
                    },
                ),
                ReferenceActionItem(
                    icon = "⌖",
                    label = "경로 확인",
                    subtitle = "개인 확장",
                    enabled = false,
                    onClick = {},
                ),
                ReferenceActionItem(
                    icon = "▧",
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
            title = "오늘의 주요 방문",
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
                primaryActionLabel = "상세 보기",
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

        ReferenceSectionHeader(
            title = "지원 & 도구",
            trailing = "더보기 ›",
            palette = palette,
        )
        ReferenceActionRow(
            items = listOf(
                ReferenceActionItem(
                    icon = "⌕",
                    label = "고객센터",
                    subtitle = "1:1 문의",
                    onClick = {},
                ),
                ReferenceActionItem(
                    icon = "□",
                    label = "부품 확인",
                    subtitle = "API 준비 중",
                    enabled = false,
                    onClick = {},
                ),
                ReferenceActionItem(
                    icon = "♢",
                    label = "안전 체크",
                    subtitle = "점검 항목",
                    onClick = {
                        primaryVisit?.let {
                            onVisitClick(it.visitId)
                        }
                    },
                ),
                ReferenceActionItem(
                    icon = "▥",
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

        ReferenceBottomNavigation(
            items = listOf(
                ReferenceBottomItem("⌂", "홈", selected = true),
                ReferenceBottomItem("▦", "방문"),
                ReferenceBottomItem("🔧", "작업"),
                ReferenceBottomItem("♢", "알림"),
                ReferenceBottomItem("♙", "마이"),
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
