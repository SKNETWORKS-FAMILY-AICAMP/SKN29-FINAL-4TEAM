package com.skn29.watercare.technician.feature.worklist

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.skn29.watercare.model.VisitScheduleStatus

data class TechnicianVisitItem(
    val visitId: String,
    val customerLabel: String,
    val productCode: String,
    val symptom: String,
    val schedule: String,
    val status: VisitScheduleStatus
)

private val demoVisits = listOf(
    TechnicianVisitItem(
        visitId = "DEMO-VISIT-002",
        customerLabel = "합성 고객 002",
        productCode = "WPUJAC104DWH",
        symptom = "출수량 저하",
        schedule = "오늘 14:00",
        status = VisitScheduleStatus.CONFIRMED
    )
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TechnicianWorkListScreen(
    onVisitClick: (String) -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("방문 업무") }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(demoVisits) { visit ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            onVisitClick(visit.visitId)
                        }
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement =
                            Arrangement.spacedBy(6.dp)
                    ) {
                        Text(
                            text = visit.customerLabel,
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text("${visit.productCode} · ${visit.symptom}")
                        Text("${visit.schedule} · ${visit.status.name}")
                    }
                }
            }
        }
    }
}
