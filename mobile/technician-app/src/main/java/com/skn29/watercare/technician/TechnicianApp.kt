@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.technician

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.UserData
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LoadingBlock
import com.skn29.watercare.core.ui.components.PendingFeatureCard
import com.skn29.watercare.core.ui.theme.WaterOrange
import kotlinx.coroutines.launch

@Composable
fun TechnicianApp() {
    var user by remember { mutableStateOf<UserData?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun demoLogin() {
        scope.launch {
            loading = true
            error = null
            when (val result = WaterCareCore.authRepository.demoLogin("DEMO-TECHNICIAN-001")) {
                is ApiResult.Success -> user = result.value.user
                is ApiResult.Failure -> error = result.message
            }
            loading = false
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text("정수기 딜러 · 방문기사", fontWeight = FontWeight.ExtraBold) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            if (user == null) {
                TechnicianHero(
                    title = "방문기사 업무를 시작하세요",
                    subtitle = "오늘 일정과 고객 정보를 쉽고 빠르게 확인할 수 있어요.",
                )
                Button(
                    onClick = ::demoLogin,
                    enabled = !loading,
                    modifier = Modifier.fillMaxWidth().height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = WaterOrange),
                ) {
                    Text("방문기사 Demo 로그인", fontWeight = FontWeight.Bold)
                }
                if (loading) LoadingBlock("로그인 중입니다")
                error?.let { ErrorCard(it, onRetry = ::demoLogin) }
                Text(
                    "현재 Backend 계약에 제공된 Demo 인증만 사용합니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                TechnicianHero(
                    title = "${user!!.displayName} 기사님",
                    subtitle = "오늘 일정과 작업 상태를 한눈에 확인해 보세요.",
                )
                if (user!!.roleCode != "TECHNICIAN") {
                    ErrorCard("방문기사 계정이 아닙니다.")
                } else {
                    ScheduleSummary()
                    NextVisitCard()
                    Text("빠른 작업", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
                    TechnicianActionGrid()
                    PendingFeatureCard(
                        "실제 방문 업무 연동",
                        "방문 목록·상세·위치·작업 완료 API가 제공되는 순서대로 연결합니다.",
                    )
                }
                TextButton(
                    onClick = {
                        scope.launch {
                            WaterCareCore.authRepository.logout()
                            user = null
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("로그아웃") }
            }
        }
    }
}

@Composable
private fun TechnicianHero(title: String, subtitle: String) {
    Surface(shape = RoundedCornerShape(30.dp), color = MaterialTheme.colorScheme.tertiaryContainer) {
        Row(
            modifier = Modifier.fillMaxWidth().heightIn(min = 180.dp).padding(18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Surface(shape = RoundedCornerShape(999.dp), color = WaterOrange) {
                    Text(
                        "방문기사용",
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 5.dp),
                        color = MaterialTheme.colorScheme.onTertiary,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Image(
                painter = painterResource(R.drawable.mascot_technician),
                contentDescription = "방문기사 캐릭터",
                modifier = Modifier.size(145.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }
}

@Composable
private fun ScheduleSummary() {
    Card(
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = WaterOrange),
    ) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("오늘 일정", color = MaterialTheme.colorScheme.onTertiary, fontWeight = FontWeight.ExtraBold)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                SummaryTile("3건", "예정 방문", Modifier.weight(1f))
                SummaryTile("1건", "진행 중", Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun SummaryTile(value: String, label: String, modifier: Modifier) {
    Surface(modifier = modifier, shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold, color = WaterOrange)
            Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun NextVisitCard() {
    Card(
        shape = RoundedCornerShape(24.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("10:30", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold, modifier = Modifier.weight(1f))
                AssistChip(onClick = {}, label = { Text("진행 중") })
            }
            Text("김○○ 고객님", fontWeight = FontWeight.ExtraBold)
            Text("서울시 강남구 테헤란로 123", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("출수량 저하 · 사전 안전 확인 완료", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun TechnicianActionGrid() {
    val actions = listOf(
        Triple("▶", "방문 시작", "업무 시작"),
        Triple("➤", "경로 안내", "고객 위치"),
        Triple("📝", "고객 메모", "필요 정보"),
        Triple("🔧", "부품 체크", "준비 부품"),
        Triple("✓", "작업 완료", "조치 저장"),
        Triple("✍", "고객 서명", "완료 확인"),
    )
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        actions.chunked(3).forEach { row ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { item ->
                    Card(
                        modifier = Modifier.weight(1f).height(132.dp),
                        shape = RoundedCornerShape(22.dp),
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
                    ) {
                        Column(
                            Modifier.fillMaxSize().padding(12.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            Text(item.first, style = MaterialTheme.typography.headlineSmall, color = WaterOrange)
                            Text(item.second, fontWeight = FontWeight.ExtraBold)
                            Text(item.third, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}
