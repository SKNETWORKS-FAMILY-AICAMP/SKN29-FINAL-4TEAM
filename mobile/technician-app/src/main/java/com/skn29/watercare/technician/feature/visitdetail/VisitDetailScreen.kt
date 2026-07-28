package com.skn29.watercare.technician.feature.visitdetail

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisitDetailScreen(
    visitId: String,
    onBack: () -> Unit,
    onRegisterResult: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("방문 상세") },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("뒤로")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = visitId,
                style = MaterialTheme.typography.titleLarge
            )
            Text("제품: WPUJAC104DWH")
            Text("증상: 출수량 저하")
            Text("우선 점검: 필터 상태, 급수·출수 계통")
            Text("공식 근거: 사용설명서 REV.00 38페이지")

            Button(onClick = onRegisterResult) {
                Text("방문 결과 등록")
            }
        }
    }
}
