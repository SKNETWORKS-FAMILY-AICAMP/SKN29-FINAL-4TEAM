package com.skn29.watercare.technician.feature.worklist

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.technician.data.dispatch.ServiceCall
import com.skn29.watercare.technician.data.dispatch.ServiceCallApi
import com.skn29.watercare.technician.data.dispatch.ServiceCallStatus
import com.skn29.watercare.technician.data.dispatch.TechnicianIdentity
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

private enum class CallTab(
    val label: String
) {
    NEW("새 콜"),
    MY("내 업무")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TechnicianWorkListScreen(
    onVisitClick: (String) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val technicianDeviceId = remember {
        TechnicianIdentity.deviceId(context)
    }

    var technicianName by rememberSaveable {
        mutableStateOf(
            TechnicianIdentity.name(context)
        )
    }
    var selectedTab by rememberSaveable {
        mutableStateOf(CallTab.NEW)
    }
    var pendingCalls by remember {
        mutableStateOf<List<ServiceCall>>(emptyList())
    }
    var myCalls by remember {
        mutableStateOf<List<ServiceCall>>(emptyList())
    }
    var loading by remember {
        mutableStateOf(true)
    }
    var acceptingId by remember {
        mutableStateOf<String?>(null)
    }
    var errorMessage by remember {
        mutableStateOf<String?>(null)
    }

    suspend fun refresh() {
        try {
            val pending = ServiceCallApi.pendingCalls()
            val assigned = ServiceCallApi.technicianCalls(
                technicianDeviceId
            )
            pendingCalls = pending
            myCalls = assigned.filter {
                it.status != ServiceCallStatus.CANCELLED
            }
            errorMessage = null
        } catch (error: Exception) {
            errorMessage =
                error.message ?: "콜 목록을 불러오지 못했습니다."
        } finally {
            loading = false
        }
    }

    LaunchedEffect(Unit) {
        while (isActive) {
            refresh()
            delay(3_000)
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor =
                        MaterialTheme.colorScheme.surface
                ),
                title = {
                    Column {
                        Text(
                            text = "방문기사 콜 센터",
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text =
                                "고객 요청을 수락하고 차량 이동을 시작합니다.",
                            style =
                                MaterialTheme.typography.bodySmall,
                            color =
                                MaterialTheme.colorScheme
                                    .onSurfaceVariant
                        )
                    }
                },
                actions = {
                    Surface(
                        color =
                            MaterialTheme.colorScheme
                                .primaryContainer,
                        shape = RoundedCornerShape(20.dp)
                    ) {
                        Text(
                            text = "기사 전용",
                            modifier = Modifier.padding(
                                horizontal = 12.dp,
                                vertical = 7.dp
                            ),
                            color =
                                MaterialTheme.colorScheme
                                    .onPrimaryContainer,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(
                start = 18.dp,
                end = 18.dp,
                top = 18.dp,
                bottom = 30.dp
            ),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                TechnicianIdentityCard(
                    technicianName = technicianName,
                    onNameChange = {
                        technicianName = it
                        TechnicianIdentity.saveName(
                            context,
                            it
                        )
                    },
                    deviceId = technicianDeviceId
                )
            }

            item {
                DashboardSummary(
                    pendingCount = pendingCalls.size,
                    activeCount = myCalls.count {
                        it.status !=
                            ServiceCallStatus.COMPLETED
                    },
                    completedCount = myCalls.count {
                        it.status ==
                            ServiceCallStatus.COMPLETED
                    }
                )
            }

            item {
                Row(
                    horizontalArrangement =
                        Arrangement.spacedBy(8.dp)
                ) {
                    CallTab.entries.forEach { tab ->
                        FilterChip(
                            selected = selectedTab == tab,
                            onClick = {
                                selectedTab = tab
                            },
                            label = {
                                Text(
                                    when (tab) {
                                        CallTab.NEW ->
                                            "${tab.label} ${pendingCalls.size}"

                                        CallTab.MY ->
                                            "${tab.label} ${myCalls.size}"
                                    }
                                )
                            }
                        )
                    }
                }
            }

            errorMessage?.let { message ->
                item {
                    ErrorBanner(message)
                }
            }

            if (loading) {
                item {
                    Text(
                        text = "서버에서 콜 목록을 불러오는 중입니다.",
                        color =
                            MaterialTheme.colorScheme
                                .onSurfaceVariant
                    )
                }
            } else {
                val visibleCalls = when (selectedTab) {
                    CallTab.NEW -> pendingCalls
                    CallTab.MY -> myCalls
                }

                if (visibleCalls.isEmpty()) {
                    item {
                        EmptyCallCard(selectedTab)
                    }
                } else {
                    items(
                        items = visibleCalls,
                        key = { it.id }
                    ) { call ->
                        TechnicianCallCard(
                            call = call,
                            isPending =
                                selectedTab == CallTab.NEW,
                            accepting =
                                acceptingId == call.id,
                            onOpen = {
                                onVisitClick(call.id)
                            },
                            onAccept = {
                                if (
                                    technicianName.isBlank()
                                ) {
                                    errorMessage =
                                        "기사 이름을 먼저 입력해 주세요."
                                } else {
                                    scope.launch {
                                        acceptingId = call.id
                                        errorMessage = null
                                        try {
                                            val accepted =
                                                ServiceCallApi.accept(
                                                    callId =
                                                        call.id,
                                                    technicianDeviceId =
                                                        technicianDeviceId,
                                                    technicianName =
                                                        technicianName.trim()
                                                )
                                            refresh()
                                            onVisitClick(
                                                accepted.id
                                            )
                                        } catch (
                                            error: Exception
                                        ) {
                                            errorMessage =
                                                error.message
                                                    ?: "콜 수락에 실패했습니다."
                                            refresh()
                                        } finally {
                                            acceptingId = null
                                        }
                                    }
                                }
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TechnicianIdentityCard(
    technicianName: String,
    onNameChange: (String) -> Unit,
    deviceId: String
) {
    Card(
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor =
                MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = "기사 프로필",
                style = MaterialTheme.typography.titleMedium,
                color =
                    MaterialTheme.colorScheme.onPrimaryContainer,
                fontWeight = FontWeight.Bold
            )
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = technicianName,
                onValueChange = onNameChange,
                label = { Text("기사 이름") },
                singleLine = true
            )
            Text(
                text = "기기 ID ${deviceId.take(8)}",
                style = MaterialTheme.typography.bodySmall,
                color =
                    MaterialTheme.colorScheme.onPrimaryContainer
            )
        }
    }
}

@Composable
private fun DashboardSummary(
    pendingCount: Int,
    activeCount: Int,
    completedCount: Int
) {
    Card(
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "실시간 업무 현황",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            SummaryLine(
                label = "수락 대기 콜",
                value = "${pendingCount}건"
            )
            SummaryLine(
                label = "내 진행 업무",
                value = "${activeCount}건"
            )
            SummaryLine(
                label = "완료 업무",
                value = "${completedCount}건"
            )
        }
    }
}

@Composable
private fun SummaryLine(
    label: String,
    value: String
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement =
            Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            color =
                MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
private fun TechnicianCallCard(
    call: ServiceCall,
    isPending: Boolean,
    accepting: Boolean,
    onOpen: () -> Unit,
    onAccept: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                enabled = !isPending,
                onClick = onOpen
            ),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(2.dp)
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.SpaceBetween
            ) {
                StatusBadge(call.status)
                Text(
                    text = call.id.take(8),
                    style =
                        MaterialTheme.typography.bodySmall,
                    color =
                        MaterialTheme.colorScheme
                            .onSurfaceVariant
                )
            }

            Text(
                text = call.customerName,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Text(
                text =
                    "${call.productName} · ${call.productModel}",
                color =
                    MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = call.symptom,
                style = MaterialTheme.typography.bodyMedium
            )

            Surface(
                color =
                    MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(14.dp)
            ) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement =
                        Arrangement.spacedBy(4.dp)
                ) {
                    Text(
                        text = call.customerAddress,
                        style =
                            MaterialTheme.typography.bodySmall
                    )
                    Text(
                        text = call.customerPhone,
                        style =
                            MaterialTheme.typography.bodySmall,
                        color =
                            MaterialTheme.colorScheme.primary
                    )
                }
            }

            if (isPending) {
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !accepting,
                    onClick = onAccept
                ) {
                    Text(
                        if (accepting) {
                            "콜 수락 처리 중..."
                        } else {
                            "콜 수락"
                        },
                        fontWeight = FontWeight.Bold
                    )
                }
            } else {
                Text(
                    text = when (call.status) {
                        ServiceCallStatus.ACCEPTED ->
                            "상세 화면에서 차량 출발"

                        ServiceCallStatus.EN_ROUTE ->
                            "GPS 위치 전송 중"

                        ServiceCallStatus.ARRIVED ->
                            "방문 결과 등록 대기"

                        ServiceCallStatus.COMPLETED ->
                            "처리 완료"

                        else ->
                            "업무 상세 확인"
                    },
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun StatusBadge(
    status: ServiceCallStatus
) {
    val container = when (status) {
        ServiceCallStatus.REQUESTED ->
            MaterialTheme.colorScheme.errorContainer

        ServiceCallStatus.ACCEPTED ->
            MaterialTheme.colorScheme.primaryContainer

        ServiceCallStatus.EN_ROUTE ->
            MaterialTheme.colorScheme.tertiaryContainer

        ServiceCallStatus.ARRIVED,
        ServiceCallStatus.COMPLETED ->
            MaterialTheme.colorScheme.secondaryContainer

        ServiceCallStatus.CANCELLED ->
            MaterialTheme.colorScheme.surfaceVariant
    }
    val content = when (status) {
        ServiceCallStatus.REQUESTED ->
            MaterialTheme.colorScheme.onErrorContainer

        ServiceCallStatus.ACCEPTED ->
            MaterialTheme.colorScheme.onPrimaryContainer

        ServiceCallStatus.EN_ROUTE ->
            MaterialTheme.colorScheme.onTertiaryContainer

        ServiceCallStatus.ARRIVED,
        ServiceCallStatus.COMPLETED ->
            MaterialTheme.colorScheme.onSecondaryContainer

        ServiceCallStatus.CANCELLED ->
            MaterialTheme.colorScheme.onSurfaceVariant
    }

    Surface(
        color = container,
        shape = RoundedCornerShape(30.dp)
    ) {
        Text(
            text = status.label,
            modifier = Modifier.padding(
                horizontal = 11.dp,
                vertical = 6.dp
            ),
            color = content,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
private fun EmptyCallCard(
    tab: CallTab
) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(20.dp)
    ) {
        Column(
            modifier = Modifier.padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp)
        ) {
            Text(
                text = if (tab == CallTab.NEW) {
                    "현재 수락 대기 중인 콜이 없습니다."
                } else {
                    "아직 수락한 업무가 없습니다."
                },
                fontWeight = FontWeight.Bold
            )
            Text(
                text =
                    "목록은 서버와 3초마다 자동 동기화됩니다.",
                style = MaterialTheme.typography.bodySmall,
                color =
                    MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun ErrorBanner(
    message: String
) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(16.dp)
    ) {
        Text(
            text = message,
            modifier = Modifier.padding(14.dp),
            color =
                MaterialTheme.colorScheme.onErrorContainer
        )
    }
}
