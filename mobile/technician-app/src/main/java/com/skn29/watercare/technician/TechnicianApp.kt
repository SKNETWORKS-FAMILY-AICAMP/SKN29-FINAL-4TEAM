@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.technician

import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassMetricTile
import com.skn29.watercare.core.ui.components.LiquidGlassPanel
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.core.ui.components.LiquidGlassTone
import com.skn29.watercare.core.ui.components.LiquidGlassToneProvider
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.PendingFeatureCard
import com.skn29.watercare.core.ui.theme.WaterCaution
import com.skn29.watercare.core.ui.theme.WaterDanger
import com.skn29.watercare.core.ui.theme.WaterGeneral
import com.skn29.watercare.core.ui.theme.WaterGradientBackground

@Composable
fun TechnicianApp() {
    LiquidGlassToneProvider(
        tone = LiquidGlassTone.TECHNICIAN,
    ) {
        TechnicianAppContent()
    }
}

@Composable
private fun TechnicianAppContent() {
    val visitRepository = remember {
        FakeTechnicianVisitRepository()
    }
    val factory = remember(visitRepository) {
        TechnicianViewModelFactory(
            authRepository = WaterCareCore.authRepository,
            backendStatusRepository =
                WaterCareCore.backendStatusRepository,
            visitRepository = visitRepository,
        )
    }
    val technicianViewModel: TechnicianViewModel =
        viewModel(factory = factory)
    val state by technicianViewModel.state
        .collectAsStateWithLifecycle()

    when {
        state.user == null -> TechnicianReferenceLogin(
            state = state,
            onLogin = technicianViewModel::demoLogin,
            onOfflinePreview =
                technicianViewModel::startOfflinePreview,
            onRetryBackend =
                technicianViewModel::checkBackend,
        )

        state.selectedVisitId == null ->
            TechnicianReferenceDashboard(
                state = state,
                onVisitClick =
                    technicianViewModel::openVisit,
                onRefresh =
                    technicianViewModel::loadVisits,
                onLogout = technicianViewModel::logout,
            )

        else -> WaterGradientBackground {
            Scaffold(
                containerColor = Color.Transparent,
                topBar = {
                    TopAppBar(
                        title = {
                            Text(
                                "방문 사전 점검",
                                fontWeight =
                                    FontWeight.ExtraBold,
                            )
                        },
                        navigationIcon = {
                            LiquidGlassButton(
                                text = "목록",
                                leadingIcon = "‹",
                                onClick =
                                    technicianViewModel::closeVisit,
                                compact = true,
                            )
                        },
                        colors =
                            TopAppBarDefaults
                                .topAppBarColors(
                                    containerColor =
                                        Color.Transparent,
                                    scrolledContainerColor =
                                        Color.White.copy(
                                            alpha = 0.72f
                                        ),
                                ),
                    )
                },
            ) { padding ->
                ReportContent(
                    state = state,
                    onBack =
                        technicianViewModel::closeVisit,
                    onRetry = {
                        state.selectedVisitId?.let(
                            technicianViewModel::openVisit
                        )
                    },
                    modifier = Modifier.padding(padding),
                )
            }
        }
    }
}
@Composable
private fun LoginContent(
    state: TechnicianUiState,
    onLogin: () -> Unit,
    onOfflinePreview: () -> Unit,
    onRetryBackend: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        TechnicianHero(
            title = "방문기사 업무를 시작하세요",
            subtitle =
                "로그인 후 배정 방문과 읽기 전용 사전 점검 내용을 확인합니다.",
        )

        LiquidGlassPanel {
            Text(
                "Backend 연결",
                fontWeight = FontWeight.ExtraBold,
            )
            Text(
                when {
                    state.checkingBackend ->
                        "연결 상태 확인 중"
                    state.backendAvailable == true ->
                        "연결 가능 · Demo 인증 사용 가능"
                    else ->
                        "연결 불가 · 합성 Fixture 미리보기만 가능"
                }
            )
            if (
                !state.checkingBackend &&
                state.backendAvailable != true
            ) {
                LiquidGlassButton(
                    text = "다시 확인",
                    onClick = onRetryBackend,
                    accent = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        LiquidGlassButton(
            text = "방문기사 Demo 로그인",
            leadingIcon = "🧰",
            onClick = onLogin,
            enabled = !state.loginLoading &&
                !state.restoringSession &&
                state.backendAvailable == true,
            accent = true,
            modifier = Modifier.fillMaxWidth(),
        )

        LiquidGlassButton(
            text = "합성 방문 Fixture 미리보기",
            leadingIcon = "◇",
            onClick = onOfflinePreview,
            enabled = !state.loginLoading &&
                !state.restoringSession,
            modifier = Modifier.fillMaxWidth(),
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
            "Demo 로그인과 저장 세션 확인은 실제 Backend 인증을 사용합니다. 앱 재실행 시 저장된 방문기사 세션을 자동 확인하며, 방문 목록과 사전 점검은 방문 API가 제공되기 전까지 합성 Fixture입니다.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun VisitListContent(
    state: TechnicianUiState,
    onVisitClick: (String) -> Unit,
    onRefresh: () -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        TechnicianHero(
            title =
                "${state.user?.displayName.orEmpty()} 기사님",
            subtitle =
                "배정 방문과 현장 전 안전 확인 정보를 먼저 확인하세요.",
        )

        LiquidGlassPanel {
            LiquidGlassPill(
                if (state.offlinePreview) {
                    "오프라인 합성 Fixture"
                } else {
                    "Demo 인증 + 합성 방문 Fixture"
                }
            )
            Text(
                "방문 API 미제공 · 실제 고객 개인정보 미사용 · Scenario ID 표시",
                style = MaterialTheme.typography.bodySmall,
            )
        }

        val confirmed = state.visits.count {
            it.scheduleStatusCode == "CONFIRMED"
        }
        val risky = state.visits.count {
            it.risk == TechnicianVisitRisk.CAUTION ||
                it.risk == TechnicianVisitRisk.DANGER
        }
        ScheduleSummary(
            total = state.visits.size,
            confirmed = confirmed,
            risky = risky,
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "배정 방문",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.ExtraBold,
                modifier = Modifier.weight(1f),
            )
            LiquidGlassButton(
                text = "새로고침",
                leadingIcon = "↻",
                onClick = onRefresh,
                compact = true,
            )
        }

        if (state.visitsLoading) {
            LoadingBlock(
                "배정 방문 목록을 불러오는 중입니다"
            )
        }
        state.error?.let {
            ErrorCard(it, onRetry = onRefresh)
        }

        if (
            !state.visitsLoading &&
            state.visits.isEmpty() &&
            state.error == null
        ) {
            LiquidGlassPanel {
                Text("현재 배정된 방문이 없습니다.")
            }
        }

        state.visits.forEach { visit ->
            VisitSummaryCard(
                visit = visit,
                onClick = {
                    onVisitClick(visit.visitId)
                },
            )
        }

        PendingFeatureCard(
            "실제 방문 업무 API",
            "방문 목록·상세 Endpoint가 제공되면 Repository만 Remote 구현으로 교체합니다. 출발·도착·완료·위치 추적은 현재 범위에 포함하지 않습니다.",
        )

        LiquidGlassButton(
            text = "로그아웃",
            onClick = onLogout,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun ScheduleSummary(
    total: Int,
    confirmed: Int,
    risky: Int,
) {
    LiquidGlassPanel(strong = true) {
        Text(
            "방문 요약",
            fontWeight = FontWeight.ExtraBold,
        )
        Row(
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            LiquidGlassMetricTile(
                value = "$total",
                label = "전체",
                modifier = Modifier.weight(1f),
            )
            LiquidGlassMetricTile(
                value = "$confirmed",
                label = "확정",
                modifier = Modifier.weight(1f),
                tint = WaterGeneral,
            )
            LiquidGlassMetricTile(
                value = "$risky",
                label = "주의·위험",
                modifier = Modifier.weight(1f),
                tint = if (risky > 0) {
                    WaterCaution
                } else {
                    WaterGeneral
                },
            )
        }
    }
}

@Composable
private fun VisitSummaryCard(
    visit: TechnicianVisitSummary,
    onClick: () -> Unit,
) {
    LiquidGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        danger = visit.risk ==
            TechnicianVisitRisk.DANGER,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                visit.scheduledAt,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.ExtraBold,
                modifier = Modifier.weight(1f),
            )
            StatusPill(visit.scheduleStatusLabel)
        }
        Text(
            "${visit.customerMaskedName} · ${visit.productModel}",
            fontWeight = FontWeight.ExtraBold,
        )
        Text(
            visit.maskedAddress,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(visit.symptomSummary)
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            RiskPill(visit.risk)
            StatusPill(visit.usageRestrictionLabel)
        }
        Text(
            "${visit.visitCode} · ${visit.scenarioId} · 합성 Fixture",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun ReportContent(
    state: TechnicianUiState,
    onBack: () -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        if (state.reportLoading) {
            LoadingBlock(
                "사전 점검 리포트를 불러오는 중입니다"
            )
        }

        state.reportError?.let {
            ErrorCard(it, onRetry = onRetry)
            LiquidGlassButton(
                text = "방문 목록으로",
                onClick = onBack,
                accent = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }

        state.selectedReport?.let { report ->
            LiquidGlassPanel(strong = true) {
                Text(
                    "읽기 전용 사전 점검",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Black,
                )
                Text(
                    "${report.visitCode} · ${report.scheduledAt}"
                )
                Text(
                    "${report.customerMaskedName} · ${report.customerMaskedPhone}",
                    fontWeight = FontWeight.Bold,
                )
                Text(report.maskedAddress)
                Text(
                    "${report.productModel} · ${report.scenarioId}"
                )
                StatusPill("합성 Fixture")
            }

            ReportSection("고객 증상 요약") {
                Text(report.symptomSummary)
            }
            ReportSection("상담 확인 내용") {
                Text(report.consultationSummary)
            }
            ReportSection("우선 점검 후보") {
                BulletList(report.inspectionCandidates)
            }
            ReportSection("안전·사용 제한") {
                Text(
                    report.safetyNotice,
                    fontWeight = FontWeight.Bold,
                )
            }
            ReportSection("금지 행동") {
                BulletList(report.prohibitedActions)
            }
            ReportSection("공식 근거") {
                report.evidence.forEach { evidence ->
                    LiquidGlassPanel(strong = true) {
                        Text(
                            evidence.documentName,
                            fontWeight = FontWeight.ExtraBold,
                        )
                        Text(
                            "${evidence.revision} · ${evidence.page}쪽"
                        )
                        Text(evidence.summary)
                        Text(
                            "검증 상태 · ${evidence.verificationStatus}",
                            style =
                                MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }

            PendingFeatureCard(
                "현장 상태 변경 기능",
                "방문 수락·출발·도착·완료 API가 아직 없으므로 이 화면은 읽기 전용입니다.",
            )

            LiquidGlassButton(
                text = "방문 목록으로",
                onClick = onBack,
                accent = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun ReportSection(
    title: String,
    content: @Composable () -> Unit,
) {
    LiquidGlassPanel {
        Text(
            title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.ExtraBold,
        )
        HorizontalDivider(
            color = Color.White.copy(alpha = 0.56f)
        )
        content()
    }
}

@Composable
private fun BulletList(
    values: List<String>,
) {
    Column(
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        values.forEach { value ->
            Text("• $value")
        }
    }
}

@Composable
private fun StatusPill(
    text: String,
) {
    LiquidGlassPill(text)
}

@Composable
private fun RiskPill(
    risk: TechnicianVisitRisk,
) {
    val color = when (risk) {
        TechnicianVisitRisk.DANGER -> WaterDanger
        TechnicianVisitRisk.CAUTION -> WaterCaution
        TechnicianVisitRisk.GENERAL -> WaterGeneral
        TechnicianVisitRisk.UNKNOWN ->
            MaterialTheme.colorScheme.onSurfaceVariant
    }

    LiquidGlassPill(
        text = "위험도 · ${risk.label}",
        tint = color,
    )
}

@Composable
private fun TechnicianHero(
    title: String,
    subtitle: String,
) {
    LiquidGlassPanel(strong = true) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 180.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                LiquidGlassPill("방문기사용")
                Text(
                    title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Black,
                )
                Text(
                    subtitle,
                    color =
                        MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Image(
                painter = painterResource(
                    R.drawable.mascot_technician
                ),
                contentDescription = "방문기사 캐릭터",
                modifier = Modifier.size(130.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }
}
