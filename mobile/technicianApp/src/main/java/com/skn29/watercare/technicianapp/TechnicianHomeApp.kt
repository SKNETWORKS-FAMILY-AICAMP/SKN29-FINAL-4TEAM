package com.skn29.watercare.technicianapp

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.skn29.watercare.KakaoMapRuntime
import com.skn29.watercare.R
import com.skn29.watercare.model.TravelMode
import com.skn29.watercare.model.VisitScheduleStatus
import com.skn29.watercare.tracking.TrackingRepository
import com.skn29.watercare.ui.map.DemoTrackingMap
import com.skn29.watercare.ui.map.KakaoTrackingMap
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val TechnicianNavy = Color(0xFF111C2E)
private val TechnicianSurface = Color(0xFFF4F7FA)
private val WaterCareTeal = Color(0xFF00A6A6)
private val SuccessGreen = Color(0xFF16865C)
private val WarningOrange = Color(0xFFE88424)

private enum class TechnicianTab(
    val label: String,
    val emoji: String
) {
    TODAY("오늘 일정", "📋"),
    CALLS("신규 콜", "🔔"),
    MAP("방문 현황", "🚙"),
    REPORT("작업 보고", "🛠️"),
    PROFILE("내 정보", "👤")
}

private enum class VisitWorkStatus {
    WAITING,
    ACCEPTED,
    EN_ROUTE,
    ARRIVED,
    WORKING,
    COMPLETED
}

private data class TechnicianVisitItem(
    val id: String,
    val time: String,
    val customerName: String,
    val address: String,
    val productName: String,
    val issue: String,
    val riskLabel: String? = null,
    val status: VisitWorkStatus
)

private val demoVisits = listOf(
    TechnicianVisitItem(
        id = "VISIT-101",
        time = "09:30",
        customerName = "김○○ 고객",
        address = "서울 중구 퇴계로 123",
        productName = "WPU-JAC104D",
        issue = "E03 · 출수량 감소",
        status = VisitWorkStatus.EN_ROUTE
    ),
    TechnicianVisitItem(
        id = "VISIT-102",
        time = "11:00",
        customerName = "박○○ 고객",
        address = "서울 용산구 한강대로 88",
        productName = "WPU-A1100",
        issue = "냉수 온도 이상",
        riskLabel = "점검 주의",
        status = VisitWorkStatus.ACCEPTED
    ),
    TechnicianVisitItem(
        id = "VISIT-103",
        time = "14:20",
        customerName = "이○○ 고객",
        address = "서울 성동구 왕십리로 42",
        productName = "WPU-B200",
        issue = "정기 필터 교체",
        status = VisitWorkStatus.WAITING
    )
)

@Composable
fun TechnicianHomeApp() {
    var selectedTab by rememberSaveable {
        mutableStateOf(TechnicianTab.TODAY)
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = TechnicianSurface,
        contentWindowInsets = WindowInsets.safeDrawing,
        bottomBar = {
            TechnicianBottomBar(
                selectedTab = selectedTab,
                onSelected = { selectedTab = it }
            )
        }
    ) { contentPadding ->
        when (selectedTab) {
            TechnicianTab.TODAY ->
                TechnicianDashboardScreen(
                    modifier = Modifier.padding(contentPadding),
                    onOpenMap = {
                        selectedTab = TechnicianTab.MAP
                    },
                    onOpenCalls = {
                        selectedTab = TechnicianTab.CALLS
                    }
                )

            TechnicianTab.CALLS ->
                TechnicianCallScreen(
                    modifier = Modifier.padding(contentPadding),
                    onOpenMap = {
                        selectedTab = TechnicianTab.MAP
                    }
                )

            TechnicianTab.MAP ->
                TechnicianMapScreen(
                    modifier =
                        Modifier.padding(
                            contentPadding
                        ),
                    onOpenReport = {
                        selectedTab =
                            TechnicianTab.REPORT
                    }
                )

            TechnicianTab.REPORT ->
                TechnicianReportScreen(
                    modifier = Modifier.padding(contentPadding)
                )

            TechnicianTab.PROFILE ->
                TechnicianProfileScreen(
                    modifier = Modifier.padding(contentPadding)
                )
        }
    }
}

@Composable
private fun TechnicianBottomBar(
    selectedTab: TechnicianTab,
    onSelected: (TechnicianTab) -> Unit
) {
    NavigationBar(
        containerColor = Color.White,
        tonalElevation = 10.dp,
        windowInsets = WindowInsets.navigationBars
    ) {
        TechnicianTab.entries.forEach { tab ->
            NavigationBarItem(
                selected = tab == selectedTab,
                onClick = { onSelected(tab) },
                icon = {
                    Text(
                        text = tab.emoji,
                        fontSize = 19.sp
                    )
                },
                label = {
                    Text(
                        text = tab.label,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        fontSize = 10.sp
                    )
                },
                colors =
                    NavigationBarItemDefaults.colors(
                        selectedIconColor =
                            WaterCareTeal,
                        selectedTextColor =
                            TechnicianNavy,
                        indicatorColor =
                            WaterCareTeal.copy(
                                alpha = 0.13f
                            ),
                        unselectedIconColor =
                            Color(0xFF7D8796),
                        unselectedTextColor =
                            Color(0xFF7D8796)
                    )
            )
        }
    }
}

@Composable
private fun TechnicianDashboardScreen(
    modifier: Modifier,
    onOpenMap: () -> Unit,
    onOpenCalls: () -> Unit
) {
    val snapshot by
        TrackingRepository.snapshot
            .collectAsStateWithLifecycle()

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 20.dp,
            top = 18.dp,
            end = 20.dp,
            bottom = 28.dp
        ),
        verticalArrangement =
            Arrangement.spacedBy(16.dp)
    ) {
        item {
            TechnicianHero()
        }

        item {
            SummarySection()
        }

        item {
            CurrentVisitStatusCard(
                status = snapshot.status,
                callAccepted =
                    snapshot.callAccepted,
                etaMinutes =
                    snapshot.etaMinutes,
                onOpenStatus =
                    if (
                        snapshot.callAccepted
                    ) {
                        onOpenMap
                    } else {
                        onOpenCalls
                    }
            )
        }

        item {
            NextVisitCard(
                onStartNavigation = onOpenCalls
            )
        }

        item {
            SectionHeader(
                title = "오늘 방문 일정",
                actionLabel = "신규 콜 보기",
                onAction = onOpenCalls
            )
        }

        items(
            items = demoVisits,
            key = { it.id }
        ) { visit ->
            VisitListCard(
                visit = visit,
                onClick = {
                    if (
                        visit.status ==
                        VisitWorkStatus.EN_ROUTE
                    ) {
                        onOpenMap()
                    }
                }
            )
        }
    }
}

@Composable
private fun TechnicianHero() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(
                RoundedCornerShape(30.dp)
            )
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        Color(0xFF082A52),
                        Color(0xFF0B3D70),
                        Color(0xFF0D507B)
                    )
                )
            )
            .padding(
                start = 22.dp,
                top = 22.dp,
                end = 12.dp,
                bottom = 20.dp
            )
    ) {
        Column {
            Row(
                modifier =
                    Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.SpaceBetween,
                verticalAlignment =
                    Alignment.Top
            ) {
                Column(
                    modifier =
                        Modifier.weight(1f)
                ) {
                    Surface(
                        color =
                            WaterCareTeal.copy(
                                alpha = 0.18f
                            ),
                        shape =
                            RoundedCornerShape(
                                99.dp
                            )
                    ) {
                        Text(
                            text =
                                "방문기사용 · PRO",
                            modifier =
                                Modifier.padding(
                                    horizontal = 11.dp,
                                    vertical = 6.dp
                                ),
                            color =
                                Color(0xFF8EFFF2),
                            fontWeight =
                                FontWeight.ExtraBold,
                            fontSize = 12.sp
                        )
                    }

                    Spacer(
                        modifier =
                            Modifier.height(14.dp)
                    )

                    Text(
                        text = "안녕하세요,\n김정수 기사님",
                        color = Color.White,
                        style =
                            MaterialTheme
                                .typography
                                .headlineMedium,
                        fontWeight =
                            FontWeight.ExtraBold
                    )

                    Spacer(
                        modifier =
                            Modifier.height(7.dp)
                    )

                    Text(
                        text =
                            "오늘도 안전하고 정확한 " +
                                "방문을 시작해요.",
                        color =
                            Color.White.copy(
                                alpha = 0.76f
                            ),
                        style =
                            MaterialTheme
                                .typography
                                .bodyMedium
                    )
                }

                Box(
                    modifier = Modifier
                        .size(128.dp)
                        .clip(
                            RoundedCornerShape(
                                26.dp
                            )
                        )
                        .background(
                            Color.White.copy(
                                alpha = 0.1f
                            )
                        ),
                    contentAlignment =
                        Alignment.Center
                ) {
                    Image(
                        painter =
                            painterResource(
                                R.drawable
                                    .mascot_water_dealer
                            ),
                        contentDescription =
                            "WaterCare 기사 모드 캐릭터",
                        modifier =
                            Modifier.size(116.dp),
                        contentScale =
                            ContentScale.Fit
                    )

                    Box(
                        modifier = Modifier
                            .align(
                                Alignment.BottomEnd
                            )
                            .clip(CircleShape)
                            .background(
                                WaterCareTeal
                            )
                            .padding(8.dp)
                    ) {
                        Text(
                            text = "🔧",
                            fontSize = 16.sp
                        )
                    }
                }
            }

            Spacer(
                modifier = Modifier.height(20.dp)
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(
                        RoundedCornerShape(
                            18.dp
                        )
                    )
                    .background(
                        Color.White.copy(
                            alpha = 0.1f
                        )
                    )
                    .padding(
                        horizontal = 14.dp,
                        vertical = 12.dp
                    ),
                verticalAlignment =
                    Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(9.dp)
                        .background(
                            Color(0xFF46E0A5),
                            CircleShape
                        )
                )

                Spacer(
                    modifier = Modifier.width(9.dp)
                )

                Text(
                    text =
                        "업무 가능 · 위치 공유 정상",
                    color = Color.White,
                    style =
                        MaterialTheme.typography
                            .labelLarge,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun SummarySection() {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement =
            Arrangement.spacedBy(10.dp)
    ) {
        SummaryCard(
            modifier = Modifier.weight(1f),
            value = "6건",
            label = "오늘 배정",
            accent = WaterCareTeal,
            icon = "📋"
        )

        SummaryCard(
            modifier = Modifier.weight(1f),
            value = "2건",
            label = "진행 중",
            accent = Color(0xFF1677E8),
            icon = "🚙"
        )

        SummaryCard(
            modifier = Modifier.weight(1f),
            value = "4건",
            label = "완료",
            accent = SuccessGreen,
            icon = "✓"
        )
    }
}

@Composable
private fun SummaryCard(
    modifier: Modifier,
    value: String,
    label: String,
    accent: Color,
    icon: String
) {
    Card(
        modifier = modifier,
        colors =
            CardDefaults.cardColors(
                containerColor = Color.White
            ),
        shape =
            RoundedCornerShape(22.dp),
        elevation =
            CardDefaults.cardElevation(
                defaultElevation = 1.dp
            )
    ) {
        Column(
            modifier = Modifier.padding(
                horizontal = 13.dp,
                vertical = 15.dp
            ),
            verticalArrangement =
                Arrangement.spacedBy(7.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .background(
                        accent.copy(
                            alpha = 0.12f
                        ),
                        CircleShape
                    ),
                contentAlignment =
                    Alignment.Center
            ) {
                Text(
                    text = icon,
                    color = accent,
                    fontWeight =
                        FontWeight.ExtraBold
                )
            }

            Text(
                text = value,
                color = TechnicianNavy,
                fontSize = 23.sp,
                fontWeight =
                    FontWeight.ExtraBold
            )

            Text(
                text = label,
                color = Color(0xFF6F7B8C),
                style =
                    MaterialTheme.typography
                        .bodySmall
            )
        }
    }
}

@Composable
private fun CurrentVisitStatusCard(
    status: VisitScheduleStatus,
    callAccepted: Boolean,
    etaMinutes: Int,
    onOpenStatus: () -> Unit
) {
    Card(
        onClick = onOpenStatus,
        colors =
            CardDefaults.cardColors(
                containerColor =
                    Color(0xFF0B355F)
            ),
        shape =
            RoundedCornerShape(26.dp)
    ) {
        Row(
            modifier = Modifier.padding(
                horizontal = 18.dp,
                vertical = 17.dp
            ),
            verticalAlignment =
                Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .background(
                        WaterCareTeal.copy(
                            alpha = 0.2f
                        ),
                        CircleShape
                    ),
                contentAlignment =
                    Alignment.Center
            ) {
                Text(
                    text = "🚙",
                    fontSize = 22.sp
                )
            }

            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 13.dp)
            ) {
                Text(
                    text = "현재 방문 현황",
                    color =
                        Color.White.copy(
                            alpha = 0.7f
                        ),
                    style =
                        MaterialTheme.typography
                            .bodyMedium
                )

                Text(
                    text =
                        technicianStatusLabel(
                            status,
                            callAccepted
                        ),
                    color = Color.White,
                    fontWeight =
                        FontWeight.ExtraBold,
                    style =
                        MaterialTheme.typography
                            .titleMedium
                )
            }

            Text(
                text =
                    if (
                        etaMinutes > 0 &&
                        status !=
                        VisitScheduleStatus
                            .COMPLETED
                    ) {
                        "${etaMinutes}분"
                    } else {
                        "확인"
                    },
                color = Color(0xFF8EFFF2),
                fontWeight =
                    FontWeight.ExtraBold
            )
        }
    }
}

@Composable
private fun NextVisitCard(
    onStartNavigation: () -> Unit
) {
    Card(
        colors =
            CardDefaults.cardColors(
                containerColor = Color.White
            ),
        shape =
            RoundedCornerShape(28.dp),
        elevation =
            CardDefaults.cardElevation(
                defaultElevation = 1.dp
            )
    ) {
        Column(
            modifier =
                Modifier.padding(20.dp),
            verticalArrangement =
                Arrangement.spacedBy(15.dp)
        ) {
            Row(
                modifier =
                    Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.SpaceBetween,
                verticalAlignment =
                    Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "다음 방문지",
                        color = TechnicianNavy,
                        style =
                            MaterialTheme
                                .typography
                                .titleLarge,
                        fontWeight =
                            FontWeight.ExtraBold
                    )

                    Text(
                        text = "1 / 6",
                        color =
                            Color(0xFF8793A1),
                        style =
                            MaterialTheme
                                .typography
                                .bodySmall
                    )
                }

                StatusPill(
                    label = "09:30 예정",
                    color = WaterCareTeal
                )
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(
                        RoundedCornerShape(
                            22.dp
                        )
                    )
                    .background(
                        Color(0xFFF4F7FA)
                    )
                    .padding(16.dp)
            ) {
                Column(
                    verticalArrangement =
                        Arrangement.spacedBy(7.dp)
                ) {
                    Text(
                        text = "김○○ 고객",
                        color = TechnicianNavy,
                        fontSize = 20.sp,
                        fontWeight =
                            FontWeight.ExtraBold
                    )

                    Text(
                        text =
                            "서울 중구 퇴계로 123",
                        color =
                            Color(0xFF687587)
                    )

                    Row(
                        horizontalArrangement =
                            Arrangement.spacedBy(
                                8.dp
                            )
                    ) {
                        MetaPill("WPU-JAC104D")
                        MetaPill("E03")
                        MetaPill("출수량 감소")
                    }
                }
            }

            Row(
                modifier =
                    Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(10.dp)
            ) {
                OutlinedButton(
                    onClick = {},
                    modifier =
                        Modifier.weight(1f),
                    shape =
                        RoundedCornerShape(
                            18.dp
                        )
                ) {
                    Text(
                        text = "고객 연락",
                        fontWeight =
                            FontWeight.Bold
                    )
                }

                Button(
                    onClick = onStartNavigation,
                    modifier =
                        Modifier.weight(1.45f),
                    colors =
                        ButtonDefaults
                            .buttonColors(
                                containerColor =
                                    TechnicianNavy
                            ),
                    shape =
                        RoundedCornerShape(
                            18.dp
                        )
                ) {
                    Text(
                        text = "콜 확인·수락",
                        fontWeight =
                            FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(
    title: String,
    actionLabel: String,
    onAction: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement =
            Arrangement.SpaceBetween,
        verticalAlignment =
            Alignment.CenterVertically
    ) {
        Text(
            text = title,
            color = TechnicianNavy,
            style =
                MaterialTheme.typography
                    .titleLarge
        )

        TextButton(onClick = onAction) {
            Text(
                text = actionLabel,
                color = WaterCareTeal,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

@Composable
private fun VisitListCard(
    visit: TechnicianVisitItem,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        colors =
            CardDefaults.cardColors(
                containerColor = Color.White
            ),
        shape = RoundedCornerShape(24.dp)
    ) {
        Row(
            modifier = Modifier.padding(18.dp),
            verticalAlignment =
                Alignment.Top
        ) {
            Column(
                horizontalAlignment =
                    Alignment.CenterHorizontally
            ) {
                Text(
                    text = visit.time,
                    color = TechnicianNavy,
                    fontWeight = FontWeight.ExtraBold
                )

                Spacer(
                    modifier = Modifier.height(8.dp)
                )

                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .background(
                            visitStatusColor(
                                visit.status
                            ),
                            CircleShape
                        )
                )
            }

            Spacer(
                modifier = Modifier.width(16.dp)
            )

            Column(
                modifier = Modifier.weight(1f)
            ) {
                Row(
                    modifier =
                        Modifier.fillMaxWidth(),
                    horizontalArrangement =
                        Arrangement.SpaceBetween
                ) {
                    Text(
                        text = visit.customerName,
                        color = TechnicianNavy,
                        fontWeight =
                            FontWeight.ExtraBold
                    )

                    StatusPill(
                        label =
                            visitStatusLabel(
                                visit.status
                            ),
                        color =
                            visitStatusColor(
                                visit.status
                            )
                    )
                }

                Spacer(
                    modifier = Modifier.height(5.dp)
                )

                Text(
                    text = visit.address,
                    color = Color(0xFF6D7889),
                    style =
                        MaterialTheme.typography
                            .bodyMedium
                )

                Spacer(
                    modifier = Modifier.height(11.dp)
                )

                Text(
                    text =
                        "${visit.productName} · " +
                            visit.issue,
                    color = TechnicianNavy,
                    fontWeight = FontWeight.SemiBold,
                    style =
                        MaterialTheme.typography
                            .bodyMedium
                )

                visit.riskLabel?.let { label ->
                    Spacer(
                        modifier =
                            Modifier.height(9.dp)
                    )

                    StatusPill(
                        label = label,
                        color = WarningOrange
                    )
                }
            }
        }
    }
}

@Composable
private fun TechnicianCallScreen(
    modifier: Modifier,
    onOpenMap: () -> Unit
) {
    val tracking by
        TrackingRepository.snapshot
            .collectAsStateWithLifecycle()

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement =
            Arrangement.spacedBy(16.dp)
    ) {
        item {
            PageTitle(
                eyebrow = "실시간 배정",
                title = "신규 방문 콜",
                description =
                    "제품·증상·위험 정보를 확인한 뒤 " +
                        "수락하세요."
            )
        }

        item {
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = Color.White
                    ),
                shape = RoundedCornerShape(28.dp)
            ) {
                Column(
                    modifier =
                        Modifier.padding(20.dp)
                ) {
                    Row(
                        modifier =
                            Modifier.fillMaxWidth(),
                        horizontalArrangement =
                            Arrangement.SpaceBetween,
                        verticalAlignment =
                            Alignment.CenterVertically
                    ) {
                        StatusPill(
                            label = "P1 일반",
                            color = WaterCareTeal
                        )

                        Text(
                            text = "방금 전",
                            color =
                                Color(0xFF7B8594)
                        )
                    }

                    Spacer(
                        modifier =
                            Modifier.height(18.dp)
                    )

                    Text(
                        text = "박○○ 고객",
                        color = TechnicianNavy,
                        fontSize = 22.sp,
                        fontWeight =
                            FontWeight.ExtraBold
                    )

                    Spacer(
                        modifier =
                            Modifier.height(5.dp)
                    )

                    Text(
                        text =
                            "서울 용산구 한강대로 88",
                        color = Color(0xFF687487)
                    )

                    Spacer(
                        modifier =
                            Modifier.height(18.dp)
                    )

                    InfoRow(
                        label = "제품",
                        value = "WPU-A1100"
                    )
                    InfoRow(
                        label = "증상",
                        value = "냉수 온도가 높음"
                    )
                    InfoRow(
                        label = "오류 코드",
                        value = "표시 없음"
                    )
                    InfoRow(
                        label = "자가조치",
                        value = "전원 재연결 완료"
                    )
                    InfoRow(
                        label = "예상 준비",
                        value = "온도 센서 점검 키트"
                    )

                    Spacer(
                        modifier =
                            Modifier.height(20.dp)
                    )

                    if (!tracking.callAccepted) {
                        Button(
                            onClick = {
                                TrackingRepository
                                    .acceptCall()
                            },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(54.dp),
                            colors =
                                ButtonDefaults
                                    .buttonColors(
                                        containerColor =
                                            TechnicianNavy
                                    ),
                            shape =
                                RoundedCornerShape(
                                    18.dp
                                )
                        ) {
                            Text(
                                text = "콜 수락",
                                fontWeight =
                                    FontWeight.Bold
                            )
                        }
                    } else {
                        Column {
                            Surface(
                                color =
                                    SuccessGreen.copy(
                                        alpha = 0.12f
                                    ),
                                shape =
                                    RoundedCornerShape(
                                        18.dp
                                    )
                            ) {
                                Text(
                                    text =
                                        "콜을 수락했습니다. " +
                                            "고객에게 기사 배정이 " +
                                            "안내됩니다.",
                                    modifier =
                                        Modifier.padding(
                                            15.dp
                                        ),
                                    color =
                                        SuccessGreen,
                                    fontWeight =
                                        FontWeight.SemiBold
                                )
                            }

                            Spacer(
                                modifier =
                                    Modifier.height(
                                        12.dp
                                    )
                            )

                            Button(
                                onClick = onOpenMap,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(54.dp),
                                colors =
                                    ButtonDefaults
                                        .buttonColors(
                                            containerColor =
                                                WaterCareTeal
                                        ),
                                shape =
                                    RoundedCornerShape(
                                        18.dp
                                    )
                            ) {
                                Text(
                                    text =
                                        "방문 경로 열기",
                                    fontWeight =
                                        FontWeight.Bold
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TechnicianMapScreen(
    modifier: Modifier,
    onOpenReport: () -> Unit
) {
    val snapshot by
        TrackingRepository.snapshot
            .collectAsStateWithLifecycle()
    val route by
        TrackingRepository.route
            .collectAsStateWithLifecycle()

    val scope = rememberCoroutineScope()

    var loadingRoute by remember {
        mutableStateOf(false)
    }
    var moving by rememberSaveable {
        mutableStateOf(false)
    }
    var routeError by remember {
        mutableStateOf<String?>(null)
    }

    suspend fun loadRoute(): Boolean {
        loadingRoute = true
        routeError = null

        TrackingRepository
            .beginRouteRetry()

        val loaded =
            TrackingRepository
                .loadRoadRoute()

        loadingRoute = false

        if (!loaded) {
            routeError =
                TrackingRepository
                    .snapshot
                    .value
                    .locationRejectedReason
        }

        return loaded
    }

    LaunchedEffect(
        snapshot.callAccepted
    ) {
        if (
            snapshot.callAccepted &&
            route.isEmpty()
        ) {
            loadRoute()
        }
    }

    LaunchedEffect(moving) {
        while (moving) {
            delay(
                TrackingRepository
                    .nextDemoDelayMillis()
            )

            val hasNext =
                TrackingRepository
                    .advanceDemoTracking()

            if (!hasNext) {
                moving = false
            }
        }
    }

    Box(
        modifier =
            modifier.fillMaxSize()
    ) {
        if (KakaoMapRuntime.isReady) {
            KakaoTrackingMap(
                route = route,
                technician =
                    snapshot
                        .technicianLocation,
                customer =
                    snapshot
                        .customerLocation,
                travelMode =
                    snapshot.travelMode,
                headingDegrees =
                    snapshot.headingDegrees,
                autoFollow = true,
                routeRecalculating =
                    snapshot
                        .routeRecalculating,
                modifier =
                    Modifier.fillMaxSize()
            )
        } else {
            DemoTrackingMap(
                route = route.ifEmpty {
                    listOf(
                        snapshot
                            .technicianLocation,
                        snapshot
                            .customerLocation
                    )
                },
                technician =
                    snapshot
                        .technicianLocation,
                customer =
                    snapshot
                        .customerLocation,
                travelMode =
                    snapshot.travelMode,
                modifier =
                    Modifier.fillMaxSize()
            )
        }

        TechnicianVisitStatusOverlay(
            status = snapshot.status,
            callAccepted =
                snapshot.callAccepted,
            etaMinutes =
                snapshot.etaMinutes,
            modifier = Modifier
                .align(
                    Alignment.TopCenter
                )
                .padding(
                    horizontal = 14.dp,
                    vertical = 12.dp
                )
        )

        Card(
            modifier = Modifier
                .align(
                    Alignment.BottomCenter
                )
                .fillMaxWidth(),
            colors =
                CardDefaults.cardColors(
                    containerColor =
                        Color.White.copy(
                            alpha = 0.98f
                        )
                ),
            elevation =
                CardDefaults.cardElevation(
                    defaultElevation = 12.dp
                ),
            shape = RoundedCornerShape(
                topStart = 30.dp,
                topEnd = 30.dp
            )
        ) {
            Column(
                modifier =
                    Modifier.padding(
                        horizontal = 18.dp,
                        vertical = 15.dp
                    ),
                verticalArrangement =
                    Arrangement.spacedBy(12.dp)
            ) {
                Box(
                    modifier = Modifier
                        .align(
                            Alignment
                                .CenterHorizontally
                        )
                        .size(
                            width = 42.dp,
                            height = 5.dp
                        )
                        .background(
                            Color(0xFFD9DFE4),
                            RoundedCornerShape(
                                99.dp
                            )
                        )
                )

                Row(
                    modifier =
                        Modifier.fillMaxWidth(),
                    horizontalArrangement =
                        Arrangement.SpaceBetween,
                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text =
                                technicianStatusLabel(
                                    snapshot.status,
                                    snapshot
                                        .callAccepted
                                ),
                            color = TechnicianNavy,
                            style =
                                MaterialTheme
                                    .typography
                                    .titleLarge,
                            fontWeight =
                                FontWeight.ExtraBold
                        )

                        Text(
                            text =
                                "김○○ 고객 · " +
                                    distanceLabel(
                                        snapshot
                                            .remainingDistanceMeters
                                    ),
                            color =
                                Color(0xFF6E7888)
                        )
                    }

                    StatusPill(
                        label = when {
                            snapshot.status ==
                                VisitScheduleStatus
                                    .COMPLETED ->
                                "완료"

                            moving ->
                                "위치 공유 중"

                            snapshot.callAccepted ->
                                "수락 완료"

                            else ->
                                "수락 대기"
                        },
                        color = when {
                            snapshot.status ==
                                VisitScheduleStatus
                                    .COMPLETED ->
                                SuccessGreen

                            moving ->
                                WaterCareTeal

                            snapshot.callAccepted ->
                                Color(0xFF1768E5)

                            else ->
                                WarningOrange
                        }
                    )
                }

                TechnicianVisitStageBar(
                    status = snapshot.status,
                    callAccepted =
                        snapshot.callAccepted
                )

                routeError?.let { message ->
                    Surface(
                        color =
                            MaterialTheme
                                .colorScheme
                                .errorContainer,
                        shape =
                            RoundedCornerShape(
                                16.dp
                            )
                    ) {
                        Text(
                            text = message,
                            modifier =
                                Modifier.padding(
                                    12.dp
                                ),
                            color =
                                MaterialTheme
                                    .colorScheme
                                    .onErrorContainer,
                            style =
                                MaterialTheme
                                    .typography
                                    .bodySmall
                        )
                    }
                }

                if (!snapshot.callAccepted) {
                    Surface(
                        color =
                            WarningOrange.copy(
                                alpha = 0.12f
                            ),
                        shape =
                            RoundedCornerShape(
                                16.dp
                            )
                    ) {
                        Text(
                            text =
                                "신규 콜에서 먼저 수락하면 " +
                                    "출발·도착·점검 상태를 " +
                                    "관리할 수 있습니다.",
                            modifier =
                                Modifier.padding(
                                    12.dp
                                ),
                            color =
                                WarningOrange,
                            fontWeight =
                                FontWeight.SemiBold,
                            style =
                                MaterialTheme
                                    .typography
                                    .bodyMedium
                        )
                    }
                }

                Row(
                    modifier =
                        Modifier.fillMaxWidth(),
                    horizontalArrangement =
                        Arrangement.spacedBy(
                            10.dp
                        )
                ) {
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                loadRoute()
                            }
                        },
                        enabled =
                            snapshot.callAccepted &&
                                !loadingRoute &&
                                snapshot.status !=
                                VisitScheduleStatus
                                    .COMPLETED,
                        modifier =
                            Modifier.weight(1f),
                        shape =
                            RoundedCornerShape(
                                18.dp
                            )
                    ) {
                        Text(
                            if (loadingRoute) {
                                "경로 확인 중"
                            } else {
                                "경로 재조회"
                            }
                        )
                    }

                    Button(
                        onClick = {
                            scope.launch {
                                when (
                                    snapshot.status
                                ) {
                                    VisitScheduleStatus
                                        .CONFIRMED -> {
                                        if (
                                            route.isEmpty()
                                        ) {
                                            val loaded =
                                                loadRoute()

                                            if (!loaded) {
                                                return@launch
                                            }
                                        }

                                        moving =
                                            TrackingRepository
                                                .startDemoTracking()
                                    }

                                    VisitScheduleStatus
                                        .EN_ROUTE,
                                    VisitScheduleStatus
                                        .NEARBY -> {
                                        moving = false
                                        TrackingRepository
                                            .markArrived()
                                    }

                                    VisitScheduleStatus
                                        .ARRIVED -> {
                                        TrackingRepository
                                            .startInspection()
                                    }

                                    VisitScheduleStatus
                                        .IN_PROGRESS -> {
                                        onOpenReport()
                                    }

                                    else -> Unit
                                }
                            }
                        },
                        enabled =
                            snapshot.callAccepted &&
                                !loadingRoute &&
                                snapshot.status !=
                                VisitScheduleStatus
                                    .COMPLETED,
                        modifier =
                            Modifier.weight(1.5f),
                        colors =
                            ButtonDefaults
                                .buttonColors(
                                    containerColor =
                                        TechnicianNavy
                                ),
                        shape =
                            RoundedCornerShape(
                                18.dp
                            )
                    ) {
                        Text(
                            text =
                                technicianPrimaryAction(
                                    snapshot.status,
                                    snapshot
                                        .callAccepted,
                                    moving
                                ),
                            fontWeight =
                                FontWeight.Bold
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TechnicianVisitStatusOverlay(
    status: VisitScheduleStatus,
    callAccepted: Boolean,
    etaMinutes: Int,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color =
            Color(0xFF0B2D55).copy(
                alpha = 0.96f
            ),
        shape =
            RoundedCornerShape(23.dp),
        shadowElevation = 7.dp
    ) {
        Row(
            modifier = Modifier.padding(
                horizontal = 17.dp,
                vertical = 14.dp
            ),
            horizontalArrangement =
                Arrangement.SpaceBetween,
            verticalAlignment =
                Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = "현재 방문 현황",
                    color =
                        Color.White.copy(
                            alpha = 0.68f
                        ),
                    style =
                        MaterialTheme.typography
                            .bodySmall
                )

                Text(
                    text =
                        technicianStatusLabel(
                            status,
                            callAccepted
                        ),
                    color = Color.White,
                    fontWeight =
                        FontWeight.ExtraBold,
                    style =
                        MaterialTheme.typography
                            .titleMedium
                )
            }

            Text(
                text =
                    if (
                        etaMinutes > 0 &&
                        status !=
                        VisitScheduleStatus
                            .COMPLETED
                    ) {
                        "약 ${etaMinutes}분"
                    } else {
                        visitStatusShortLabel(
                            status,
                            callAccepted
                        )
                    },
                color = Color(0xFF8EFFF2),
                fontWeight =
                    FontWeight.ExtraBold
            )
        }
    }
}

@Composable
private fun TechnicianVisitStageBar(
    status: VisitScheduleStatus,
    callAccepted: Boolean
) {
    val currentIndex = when {
        status ==
            VisitScheduleStatus
                .COMPLETED ->
            4

        status ==
            VisitScheduleStatus
                .IN_PROGRESS ->
            3

        status ==
            VisitScheduleStatus
                .ARRIVED ->
            2

        status ==
            VisitScheduleStatus
                .EN_ROUTE ||
        status ==
            VisitScheduleStatus
                .NEARBY ->
            1

        callAccepted ->
            0

        else ->
            -1
    }

    val labels = listOf(
        "수락",
        "출발",
        "도착",
        "점검",
        "완료"
    )

    Row(
        modifier =
            Modifier.fillMaxWidth(),
        horizontalArrangement =
            Arrangement.SpaceBetween
    ) {
        labels.forEachIndexed {
                index,
                label ->
            Column(
                horizontalAlignment =
                    Alignment.CenterHorizontally
            ) {
                Box(
                    modifier = Modifier
                        .size(26.dp)
                        .background(
                            if (
                                index <=
                                currentIndex
                            ) {
                                WaterCareTeal
                            } else {
                                Color(
                                    0xFFDDE3E7
                                )
                            },
                            CircleShape
                        ),
                    contentAlignment =
                        Alignment.Center
                ) {
                    Text(
                        text =
                            if (
                                index <=
                                currentIndex
                            ) {
                                "✓"
                            } else {
                                "${index + 1}"
                            },
                        color =
                            if (
                                index <=
                                currentIndex
                            ) {
                                Color.White
                            } else {
                                Color(
                                    0xFF7C8994
                                )
                            },
                        fontWeight =
                            FontWeight.Bold,
                        style =
                            MaterialTheme
                                .typography
                                .labelSmall
                    )
                }

                Spacer(
                    modifier =
                        Modifier.height(3.dp)
                )

                Text(
                    text = label,
                    color =
                        if (
                            index <=
                            currentIndex
                        ) {
                            TechnicianNavy
                        } else {
                            Color(0xFF89959F)
                        },
                    fontWeight =
                        FontWeight.SemiBold,
                    style =
                        MaterialTheme.typography
                            .labelSmall
                )
            }
        }
    }
}

@Composable
private fun TechnicianReportScreen(
    modifier: Modifier
) {
    val snapshot by
        TrackingRepository.snapshot
            .collectAsStateWithLifecycle()

    var selectedResult by rememberSaveable {
        mutableStateOf("정상 처리")
    }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement =
            Arrangement.spacedBy(16.dp)
    ) {
        item {
            PageTitle(
                eyebrow = "방문 후 기록",
                title = "작업 보고",
                description =
                    "점검 결과를 저장하면 고객 케어 이력과 " +
                        "후속 상담에 연결됩니다."
            )
        }

        item {
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor = Color.White
                    ),
                shape = RoundedCornerShape(28.dp)
            ) {
                Column(
                    modifier =
                        Modifier.padding(20.dp)
                ) {
                    Text(
                        text = "VISIT-101",
                        color = WaterCareTeal,
                        fontWeight =
                            FontWeight.ExtraBold
                    )

                    Spacer(
                        modifier =
                            Modifier.height(4.dp)
                    )

                    Text(
                        text = "김○○ 고객 · WPU-JAC104D",
                        color = TechnicianNavy,
                        style =
                            MaterialTheme.typography
                                .titleLarge
                    )

                    Spacer(
                        modifier =
                            Modifier.height(18.dp)
                    )

                    Text(
                        text = "처리 결과",
                        color = TechnicianNavy,
                        fontWeight = FontWeight.Bold
                    )

                    Spacer(
                        modifier =
                            Modifier.height(8.dp)
                    )

                    Row(
                        horizontalArrangement =
                            Arrangement.spacedBy(8.dp)
                    ) {
                        listOf(
                            "정상 처리",
                            "부품 교체",
                            "재방문 필요"
                        ).forEach { result ->
                            FilterChip(
                                selected =
                                    result ==
                                        selectedResult,
                                onClick = {
                                    selectedResult =
                                        result
                                },
                                label = {
                                    Text(result)
                                }
                            )
                        }
                    }

                    Spacer(
                        modifier =
                            Modifier.height(20.dp)
                    )

                    ReportField(
                        label = "실제 원인",
                        value =
                            "급수 필터 내부 이물로 인한 " +
                                "유량 저하"
                    )
                    ReportField(
                        label = "조치 내용",
                        value =
                            "필터 세척 및 급수 라인 점검"
                    )
                    ReportField(
                        label = "교체 부품",
                        value = "없음"
                    )
                    ReportField(
                        label = "기사 메모",
                        value =
                            "3개월 후 필터 교체 알림 권장"
                    )

                    Spacer(
                        modifier =
                            Modifier.height(18.dp)
                    )

                    Button(
                        onClick = {
                            TrackingRepository
                                .completeVisit()
                        },
                        enabled =
                            snapshot.status !=
                            VisitScheduleStatus
                                .COMPLETED,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(54.dp),
                        colors =
                            ButtonDefaults
                                .buttonColors(
                                    containerColor =
                                        TechnicianNavy
                                ),
                        shape =
                            RoundedCornerShape(
                                18.dp
                            )
                    ) {
                        Text(
                            text =
                                if (
                                    snapshot.status ==
                                    VisitScheduleStatus
                                        .COMPLETED
                                ) {
                                    "방문 완료 저장됨"
                                } else {
                                    "방문 완료 저장"
                                },
                            fontWeight =
                                FontWeight.Bold
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TechnicianProfileScreen(
    modifier: Modifier
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement =
            Arrangement.spacedBy(14.dp)
    ) {
        item {
            PageTitle(
                eyebrow = "WaterCare Pro",
                title = "기사 정보",
                description =
                    "업무 상태와 차량·연락 정보를 관리합니다."
            )
        }

        item {
            Card(
                colors =
                    CardDefaults.cardColors(
                        containerColor =
                            TechnicianNavy
                    ),
                shape = RoundedCornerShape(28.dp)
            ) {
                Row(
                    modifier =
                        Modifier.padding(22.dp),
                    verticalAlignment =
                        Alignment.CenterVertically
                ) {
                    Surface(
                        modifier =
                            Modifier.size(62.dp),
                        shape = CircleShape,
                        color =
                            WaterCareTeal.copy(
                                alpha = 0.2f
                            )
                    ) {
                        Box(
                            contentAlignment =
                                Alignment.Center
                        ) {
                            Text(
                                text = "김",
                                color =
                                    Color(0xFF8EFFF2),
                                fontSize = 23.sp,
                                fontWeight =
                                    FontWeight.ExtraBold
                            )
                        }
                    }

                    Spacer(
                        modifier =
                            Modifier.width(16.dp)
                    )

                    Column {
                        Text(
                            text = "김정수 기사",
                            color = Color.White,
                            fontSize = 21.sp,
                            fontWeight =
                                FontWeight.ExtraBold
                        )

                        Spacer(
                            modifier =
                                Modifier.height(4.dp)
                        )

                        Text(
                            text =
                                "서울 중부 서비스팀",
                            color =
                                Color.White.copy(
                                    alpha = 0.72f
                                )
                        )
                    }
                }
            }
        }

        item {
            ProfileSettingCard(
                title = "업무 상태",
                value = "업무 가능",
                accent = SuccessGreen
            )
        }

        item {
            ProfileSettingCard(
                title = "차량 정보",
                value = "12가 3456 · 서비스 차량",
                accent = WaterCareTeal
            )
        }

        item {
            ProfileSettingCard(
                title = "위치 공유",
                value = "방문 업무 중에만 사용",
                accent = WarningOrange
            )
        }

        item {
            ProfileSettingCard(
                title = "오늘 동기화",
                value = "방금 완료",
                accent = Color(0xFF765BD8)
            )
        }
    }
}

@Composable
private fun PageTitle(
    eyebrow: String,
    title: String,
    description: String
) {
    Column {
        Text(
            text = eyebrow,
            color = WaterCareTeal,
            fontWeight = FontWeight.ExtraBold
        )

        Spacer(
            modifier = Modifier.height(6.dp)
        )

        Text(
            text = title,
            color = TechnicianNavy,
            style =
                MaterialTheme.typography
                    .headlineMedium
        )

        Spacer(
            modifier = Modifier.height(8.dp)
        )

        Text(
            text = description,
            color = Color(0xFF657183),
            style =
                MaterialTheme.typography
                    .bodyLarge
        )
    }
}

@Composable
private fun StatusPill(
    label: String,
    color: Color
) {
    Surface(
        color = color.copy(alpha = 0.12f),
        shape = RoundedCornerShape(99.dp)
    ) {
        Text(
            text = label,
            modifier = Modifier.padding(
                horizontal = 11.dp,
                vertical = 6.dp
            ),
            color = color,
            fontSize = 12.sp,
            fontWeight = FontWeight.ExtraBold
        )
    }
}

@Composable
private fun MetaPill(
    label: String
) {
    Surface(
        color = Color(0xFFF0F4F7),
        shape = RoundedCornerShape(99.dp)
    ) {
        Text(
            text = label,
            modifier = Modifier.padding(
                horizontal = 10.dp,
                vertical = 6.dp
            ),
            color = Color(0xFF536073),
            fontSize = 12.sp,
            fontWeight = FontWeight.SemiBold
        )
    }
}

@Composable
private fun InfoRow(
    label: String,
    value: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 9.dp),
        horizontalArrangement =
            Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            color = Color(0xFF7A8492)
        )

        Text(
            text = value,
            color = TechnicianNavy,
            fontWeight = FontWeight.SemiBold
        )
    }

    HorizontalDivider(
        color = Color(0xFFEDF0F3)
    )
}

@Composable
private fun ReportField(
    label: String,
    value: String
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
    ) {
        Text(
            text = label,
            color = Color(0xFF7A8492),
            style =
                MaterialTheme.typography
                    .bodyMedium
        )

        Spacer(
            modifier = Modifier.height(5.dp)
        )

        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = Color(0xFFF5F7F9),
            shape = RoundedCornerShape(16.dp)
        ) {
            Text(
                text = value,
                modifier = Modifier.padding(14.dp),
                color = TechnicianNavy,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}

@Composable
private fun ProfileSettingCard(
    title: String,
    value: String,
    accent: Color
) {
    Card(
        colors =
            CardDefaults.cardColors(
                containerColor = Color.White
            ),
        shape = RoundedCornerShape(22.dp)
    ) {
        Row(
            modifier = Modifier.padding(18.dp),
            verticalAlignment =
                Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .background(
                        accent,
                        CircleShape
                    )
            )

            Spacer(
                modifier = Modifier.width(14.dp)
            )

            Column {
                Text(
                    text = title,
                    color = TechnicianNavy,
                    fontWeight = FontWeight.Bold
                )

                Spacer(
                    modifier = Modifier.height(3.dp)
                )

                Text(
                    text = value,
                    color = Color(0xFF707B8B)
                )
            }
        }
    }
}

private fun visitStatusLabel(
    status: VisitWorkStatus
): String = when (status) {
    VisitWorkStatus.WAITING -> "대기"
    VisitWorkStatus.ACCEPTED -> "수락"
    VisitWorkStatus.EN_ROUTE -> "이동 중"
    VisitWorkStatus.ARRIVED -> "도착"
    VisitWorkStatus.WORKING -> "점검 중"
    VisitWorkStatus.COMPLETED -> "완료"
}

private fun visitStatusColor(
    status: VisitWorkStatus
): Color = when (status) {
    VisitWorkStatus.WAITING ->
        Color(0xFF7A8492)

    VisitWorkStatus.ACCEPTED ->
        Color(0xFF765BD8)

    VisitWorkStatus.EN_ROUTE ->
        WaterCareTeal

    VisitWorkStatus.ARRIVED ->
        WarningOrange

    VisitWorkStatus.WORKING ->
        Color(0xFF1768E5)

    VisitWorkStatus.COMPLETED ->
        SuccessGreen
}

private fun technicianStatusLabel(
    status: VisitScheduleStatus,
    callAccepted: Boolean
): String = when {
    status ==
        VisitScheduleStatus.COMPLETED ->
        "방문 작업 완료"

    status ==
        VisitScheduleStatus.IN_PROGRESS ->
        "현장 점검 진행 중"

    status ==
        VisitScheduleStatus.ARRIVED ->
        "고객 위치 도착"

    status ==
        VisitScheduleStatus.NEARBY ->
        "고객 위치 근처 도착"

    status ==
        VisitScheduleStatus.EN_ROUTE ->
        "고객님 댁으로 이동 중"

    callAccepted ->
        "콜 수락 · 출발 준비"

    else ->
        "신규 콜 수락 대기"
}

private fun visitStatusShortLabel(
    status: VisitScheduleStatus,
    callAccepted: Boolean
): String = when {
    status ==
        VisitScheduleStatus.COMPLETED ->
        "완료"

    status ==
        VisitScheduleStatus.IN_PROGRESS ->
        "점검 중"

    status ==
        VisitScheduleStatus.ARRIVED ->
        "도착"

    status ==
        VisitScheduleStatus.NEARBY ->
        "근처"

    status ==
        VisitScheduleStatus.EN_ROUTE ->
        "이동 중"

    callAccepted ->
        "수락"

    else ->
        "대기"
}

private fun technicianPrimaryAction(
    status: VisitScheduleStatus,
    callAccepted: Boolean,
    moving: Boolean
): String = when {
    !callAccepted ->
        "콜 수락 후 시작"

    moving ->
        "이동 중"

    status ==
        VisitScheduleStatus.CONFIRMED ->
        "출발 및 위치 공유"

    status ==
        VisitScheduleStatus.EN_ROUTE ||
    status ==
        VisitScheduleStatus.NEARBY ->
        "현장 도착"

    status ==
        VisitScheduleStatus.ARRIVED ->
        "점검 시작"

    status ==
        VisitScheduleStatus.IN_PROGRESS ->
        "작업 보고 작성"

    status ==
        VisitScheduleStatus.COMPLETED ->
        "방문 완료"

    else ->
        "방문 현황 확인"
}

private fun distanceLabel(
    meters: Int
): String = when {
    meters <= 0 -> "거리 계산 중"
    meters < 1_000 -> "${meters}m 남음"
    else ->
        String.format(
            "%.1fkm 남음",
            meters / 1_000.0
        )
}

private fun travelHeadline(
    mode: TravelMode,
    moving: Boolean
): String = when {
    moving && mode == TravelMode.DRIVING ->
        "고객님 댁으로 이동 중"

    mode == TravelMode.WALKING ->
        "차량에서 내려 이동 중"

    mode == TravelMode.ARRIVED ->
        "고객 위치에 도착"

    else ->
        "출발 준비가 완료됐어요"
}
