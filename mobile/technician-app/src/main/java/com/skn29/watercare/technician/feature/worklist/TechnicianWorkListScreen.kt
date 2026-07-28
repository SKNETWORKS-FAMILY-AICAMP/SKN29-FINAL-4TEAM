package com.skn29.watercare.technician.feature.worklist

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.technician.data.TechnicianDemoData
import com.skn29.watercare.technician.data.TechnicianVisit
import com.skn29.watercare.technician.data.TechnicianVisitStatus

private enum class WorkFilter(
    val label: String
) {
    ALL("전체"),
    TODAY("오늘"),
    URGENT("긴급")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TechnicianWorkListScreen(
    onVisitClick: (String) -> Unit
) {
    var selectedFilter by remember {
        mutableStateOf(WorkFilter.ALL)
    }

    val visits = remember(selectedFilter) {
        when (selectedFilter) {
            WorkFilter.ALL -> TechnicianDemoData.visits
            WorkFilter.TODAY -> TechnicianDemoData.visits.filter {
                it.schedule.startsWith("오늘")
            }
            WorkFilter.URGENT -> TechnicianDemoData.visits.filter {
                it.status == TechnicianVisitStatus.URGENT
            }
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                title = {
                    Column {
                        Text(
                            text = "방문기사 업무",
                            style = MaterialTheme.typography.titleLarge
                        )
                        Text(
                            text = "양정현 기사 · 서울 동부 권역",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    Surface(
                        color = MaterialTheme.colorScheme.primaryContainer,
                        shape = RoundedCornerShape(20.dp)
                    ) {
                        Text(
                            text = "기사 전용",
                            modifier = Modifier.padding(
                                horizontal = 12.dp,
                                vertical = 7.dp
                            ),
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(Modifier.padding(end = 8.dp))
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
                bottom = 28.dp
            ),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                Column(
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Text(
                        text = "오늘의 업무 현황",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        SummaryCard(
                            modifier = Modifier.width(96.dp),
                            value = "2건",
                            label = "오늘 방문",
                            accent = MaterialTheme.colorScheme.primary
                        )
                        SummaryCard(
                            modifier = Modifier.width(96.dp),
                            value = "1건",
                            label = "긴급 점검",
                            accent = MaterialTheme.colorScheme.error
                        )
                        SummaryCard(
                            modifier = Modifier.width(96.dp),
                            value = "0건",
                            label = "처리 완료",
                            accent = MaterialTheme.colorScheme.tertiary
                        )
                    }

                    Surface(
                        color = MaterialTheme.colorScheme.secondaryContainer,
                        shape = RoundedCornerShape(18.dp)
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(5.dp)
                        ) {
                            Text(
                                text = "기사 업무 흐름",
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSecondaryContainer
                            )
                            Text(
                                text = "배정 업무 확인 → 고객·제품 사전 점검 → 방문 결과 등록",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSecondaryContainer
                            )
                        }
                    }

                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        WorkFilter.entries.forEach { filter ->
                            FilterChip(
                                selected = selectedFilter == filter,
                                onClick = { selectedFilter = filter },
                                label = { Text(filter.label) }
                            )
                        }
                    }
                }
            }

            items(
                items = visits,
                key = { it.visitId }
            ) { visit ->
                TechnicianVisitCard(
                    visit = visit,
                    onClick = {
                        onVisitClick(visit.visitId)
                    }
                )
            }
        }
    }
}

@Composable
private fun SummaryCard(
    modifier: Modifier,
    value: String,
    label: String,
    accent: Color
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = 1.dp
        )
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp)
        ) {
            Text(
                text = value,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.ExtraBold,
                color = accent
            )
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun TechnicianVisitCard(
    visit: TechnicianVisit,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = 2.dp
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                StatusBadge(status = visit.status)

                Text(
                    text = visit.schedule,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold
                )
            }

            Text(
                text = visit.customerName,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )

            Text(
                text = "${visit.productName} · ${visit.productCode}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Text(
                text = visit.symptom,
                style = MaterialTheme.typography.bodyMedium
            )

            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(14.dp)
            ) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(
                        text = visit.address,
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(
                        text = "현재 위치에서 약 ${visit.distanceKm}km",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            Text(
                text = "업무 상세 확인",
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.primary,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

@Composable
private fun StatusBadge(
    status: TechnicianVisitStatus
) {
    val containerColor = when (status) {
        TechnicianVisitStatus.URGENT ->
            MaterialTheme.colorScheme.errorContainer

        TechnicianVisitStatus.EN_ROUTE,
        TechnicianVisitStatus.IN_PROGRESS ->
            MaterialTheme.colorScheme.tertiaryContainer

        TechnicianVisitStatus.COMPLETED ->
            MaterialTheme.colorScheme.secondaryContainer

        TechnicianVisitStatus.CONFIRMED ->
            MaterialTheme.colorScheme.primaryContainer
    }

    val contentColor = when (status) {
        TechnicianVisitStatus.URGENT ->
            MaterialTheme.colorScheme.onErrorContainer

        TechnicianVisitStatus.EN_ROUTE,
        TechnicianVisitStatus.IN_PROGRESS ->
            MaterialTheme.colorScheme.onTertiaryContainer

        TechnicianVisitStatus.COMPLETED ->
            MaterialTheme.colorScheme.onSecondaryContainer

        TechnicianVisitStatus.CONFIRMED ->
            MaterialTheme.colorScheme.onPrimaryContainer
    }

    Surface(
        color = containerColor,
        shape = RoundedCornerShape(30.dp)
    ) {
        Text(
            text = status.label,
            modifier = Modifier.padding(
                horizontal = 11.dp,
                vertical = 6.dp
            ),
            color = contentColor,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold
        )
    }
}
