@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.technician

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.PendingFeatureCard
import com.skn29.watercare.core.ui.theme.WaterCaution
import com.skn29.watercare.core.ui.theme.WaterDanger
import com.skn29.watercare.core.ui.theme.WaterGeneral
import com.skn29.watercare.core.ui.theme.WaterGradientBackground
import com.skn29.watercare.core.ui.theme.WaterOrange

@Composable
fun TechnicianApp() {
    val visitRepository = remember { FakeTechnicianVisitRepository() }
    val factory = remember(visitRepository) {
        TechnicianViewModelFactory(
            authRepository = WaterCareCore.authRepository,
            backendStatusRepository = WaterCareCore.backendStatusRepository,
            visitRepository = visitRepository,
        )
    }
    val technicianViewModel: TechnicianViewModel = viewModel(factory = factory)
    val state by technicianViewModel.state.collectAsStateWithLifecycle()

    WaterGradientBackground {
        Scaffold(
        containerColor = Color.Transparent,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        if (state.selectedVisitId == null) {
                            "정수기 딜러 · 방문기사"
                        } else {
                            "방문 사전 점검"
                        },
                        fontWeight = FontWeight.ExtraBold,
                    )
                },
                navigationIcon = {
                    if (state.selectedVisitId != null) {
                        TextButton(onClick = technicianViewModel::closeVisit) {
                            Text("목록")
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color.Transparent,
                ),
            )
        },
    ) { padding ->
        when {
            state.user == null -> LoginContent(
                state = state,
                onLogin = technicianViewModel::demoLogin,
                onOfflinePreview = technicianViewModel::startOfflinePreview,
                onRetryBackend = technicianViewModel::checkBackend,
                modifier = Modifier.padding(padding),
            )

            state.selectedVisitId != null -> ReportContent(
                state = state,
                onBack = technicianViewModel::closeVisit,
                onRetry = {
                    state.selectedVisitId?.let(technicianViewModel::openVisit)
                },
                modifier = Modifier.padding(padding),
            )

            else -> VisitListContent(
                state = state,
                onVisitClick = technicianViewModel::openVisit,
                onRefresh = technicianViewModel::loadVisits,
                onLogout = technicianViewModel::logout,
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
            subtitle = "로그인 후 배정 방문과 읽기 전용 사전 점검 내용을 확인합니다.",
        )

        Card(
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface,
            ),
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Backend 연결", fontWeight = FontWeight.ExtraBold)
                Text(
                    when {
                        state.checkingBackend -> "연결 상태 확인 중"
                        state.backendAvailable == true -> "연결 가능 · Demo 인증 사용 가능"
                        else -> "연결 불가 · 합성 Fixture 미리보기만 가능"
                    }
                )
                if (!state.checkingBackend && state.backendAvailable != true) {
                    TextButton(onClick = onRetryBackend) {
                        Text("다시 확인")
                    }
                }
            }
        }

        Button(
            onClick = onLogin,
            enabled = !state.loginLoading && !state.restoringSession && state.backendAvailable == true,
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp),
            colors = ButtonDefaults.buttonColors(containerColor = WaterOrange),
        ) {
            Text("방문기사 Demo 로그인", fontWeight = FontWeight.Bold)
        }

        OutlinedButton(
            onClick = onOfflinePreview,
            enabled = !state.loginLoading && !state.restoringSession,
            modifier = Modifier
                .fillMaxWidth()
                .height(54.dp),
        ) {
            Text("합성 방문 Fixture 미리보기")
        }

        if (state.restoringSession) {
            LoadingBlock("저장된 방문기사 세션을 확인하는 중입니다")
        }
        if (state.loginLoading) {
            LoadingBlock("방문기사 계정을 확인하는 중입니다")
        }
        state.error?.let { ErrorCard(it, onRetry = onLogin) }

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
            title = "${state.user?.displayName.orEmpty()} 기사님",
            subtitle = "배정 방문과 현장 전 안전 확인 정보를 먼저 확인하세요.",
        )

        Surface(
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.secondaryContainer,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(15.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    if (state.offlinePreview) {
                        "오프라인 합성 Fixture"
                    } else {
                        "Demo 인증 + 합성 방문 Fixture"
                    },
                    fontWeight = FontWeight.ExtraBold,
                )
                Text(
                    "방문 API 미제공 · 실제 고객 개인정보 미사용 · Scenario ID 표시",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }

        val confirmed = state.visits.count { it.scheduleStatusCode == "CONFIRMED" }
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
            TextButton(onClick = onRefresh) {
                Text("새로고침")
            }
        }

        if (state.visitsLoading) {
            LoadingBlock("배정 방문 목록을 불러오는 중입니다")
        }
        state.error?.let { ErrorCard(it, onRetry = onRefresh) }

        if (!state.visitsLoading && state.visits.isEmpty() && state.error == null) {
            Card(shape = RoundedCornerShape(22.dp)) {
                Text(
                    "현재 배정된 방문이 없습니다.",
                    modifier = Modifier.padding(18.dp),
                )
            }
        }

        state.visits.forEach { visit ->
            VisitSummaryCard(
                visit = visit,
                onClick = { onVisitClick(visit.visitId) },
            )
        }

        PendingFeatureCard(
            "실제 방문 업무 API",
            "방문 목록·상세 Endpoint가 제공되면 Repository만 Remote 구현으로 교체합니다. 출발·도착·완료·위치 추적은 현재 범위에 포함하지 않습니다.",
        )

        TextButton(
            onClick = onLogout,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("로그아웃")
        }
    }
}

@Composable
private fun ScheduleSummary(
    total: Int,
    confirmed: Int,
    risky: Int,
) {
    Card(
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = WaterOrange),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "방문 요약",
                color = MaterialTheme.colorScheme.onTertiary,
                fontWeight = FontWeight.ExtraBold,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SummaryTile("$total", "전체", Modifier.weight(1f))
                SummaryTile("$confirmed", "확정", Modifier.weight(1f))
                SummaryTile("$risky", "주의·위험", Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun SummaryTile(
    value: String,
    label: String,
    modifier: Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier.padding(13.dp),
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            Text(
                value,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.ExtraBold,
                color = WaterOrange,
            )
            Text(
                label,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun VisitSummaryCard(
    visit: TechnicianVisitSummary,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (visit.risk == TechnicianVisitRisk.DANGER) {
                MaterialTheme.colorScheme.errorContainer
            } else {
                MaterialTheme.colorScheme.surface
            },
        ),
        border = BorderStroke(
            1.dp,
            if (visit.risk == TechnicianVisitRisk.DANGER) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.outline
            },
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
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
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
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
            LoadingBlock("사전 점검 리포트를 불러오는 중입니다")
        }

        state.reportError?.let {
            ErrorCard(it, onRetry = onRetry)
            OutlinedButton(
                onClick = onBack,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("방문 목록으로")
            }
        }

        state.selectedReport?.let { report ->
            Surface(
                shape = RoundedCornerShape(24.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                border = BorderStroke(
                    1.dp,
                    MaterialTheme.colorScheme.outline,
                ),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        "읽기 전용 사전 점검",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.ExtraBold,
                    )
                    Text("${report.visitCode} · ${report.scheduledAt}")
                    Text(
                        "${report.customerMaskedName} · ${report.customerMaskedPhone}",
                        fontWeight = FontWeight.Bold,
                    )
                    Text(report.maskedAddress)
                    Text("${report.productModel} · ${report.scenarioId}")
                    StatusPill("합성 Fixture")
                }
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
                Text(report.safetyNotice, fontWeight = FontWeight.Bold)
            }
            ReportSection("금지 행동") {
                BulletList(report.prohibitedActions)
            }
            ReportSection("공식 근거") {
                report.evidence.forEach { evidence ->
                    Surface(
                        shape = RoundedCornerShape(18.dp),
                        color = MaterialTheme.colorScheme.secondaryContainer,
                    ) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(5.dp),
                        ) {
                            Text(evidence.documentName, fontWeight = FontWeight.ExtraBold)
                            Text("${evidence.revision} · ${evidence.page}쪽")
                            Text(evidence.summary)
                            Text(
                                "검증 상태 · ${evidence.verificationStatus}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }

            PendingFeatureCard(
                "현장 상태 변경 기능",
                "방문 수락·출발·도착·완료 API가 아직 없으므로 이 화면은 읽기 전용입니다.",
            )

            OutlinedButton(
                onClick = onBack,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("방문 목록으로")
            }
        }
    }
}

@Composable
private fun ReportSection(
    title: String,
    content: @Composable () -> Unit,
) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.ExtraBold,
            )
            HorizontalDivider()
            content()
        }
    }
}

@Composable
private fun BulletList(
    values: List<String>,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        values.forEach { value ->
            Text("• $value")
        }
    }
}

@Composable
private fun StatusPill(
    text: String,
) {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = MaterialTheme.colorScheme.secondaryContainer,
    ) {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun RiskPill(
    risk: TechnicianVisitRisk,
) {
    val color = when (risk) {
        TechnicianVisitRisk.DANGER -> WaterDanger
        TechnicianVisitRisk.CAUTION -> WaterCaution
        TechnicianVisitRisk.GENERAL -> WaterGeneral
        TechnicianVisitRisk.UNKNOWN -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    Surface(
        shape = RoundedCornerShape(999.dp),
        color = color.copy(alpha = 0.13f),
        border = BorderStroke(
            1.dp,
            color.copy(alpha = 0.36f),
        ),
    ) {
        Text(
            "위험도 · ${risk.label}",
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            style = MaterialTheme.typography.bodySmall,
            color = color,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun TechnicianHero(
    title: String,
    subtitle: String,
) {
    Surface(
        shape = RoundedCornerShape(24.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 180.dp)
                .padding(18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = WaterOrange,
                ) {
                    Text(
                        "방문기사용",
                        modifier = Modifier.padding(
                            horizontal = 12.dp,
                            vertical = 5.dp,
                        ),
                        color = MaterialTheme.colorScheme.onTertiary,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Text(
                    title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.ExtraBold,
                )
                Text(
                    subtitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Image(
                painter = painterResource(R.drawable.mascot_technician),
                contentDescription = "방문기사 캐릭터",
                modifier = Modifier.size(130.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }
}
