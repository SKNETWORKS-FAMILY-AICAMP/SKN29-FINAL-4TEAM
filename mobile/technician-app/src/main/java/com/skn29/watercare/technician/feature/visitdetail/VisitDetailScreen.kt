package com.skn29.watercare.technician.feature.visitdetail

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.technician.data.TechnicianDemoData
import com.skn29.watercare.technician.data.TechnicianVisit

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VisitDetailScreen(
    visitId: String,
    onBack: () -> Unit,
    onRegisterResult: () -> Unit
) {
    val visit = TechnicianDemoData.findVisit(visitId)
    val context = LocalContext.current
    var visitStarted by rememberSaveable {
        mutableStateOf(false)
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                title = {
                    Text("방문 업무 상세")
                },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("뒤로")
                    }
                }
            )
        }
    ) { padding ->
        if (visit == null) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(24.dp),
                verticalArrangement = Arrangement.Center
            ) {
                Text(
                    text = "방문 정보를 찾을 수 없습니다.",
                    style = MaterialTheme.typography.titleMedium
                )
            }
            return@Scaffold
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(
                    start = 18.dp,
                    end = 18.dp,
                    top = 18.dp,
                    bottom = 30.dp
                ),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            VisitStatusHeader(
                visit = visit,
                visitStarted = visitStarted
            )

            SectionCard(
                title = "고객 및 방문 정보"
            ) {
                InfoRow("고객", visit.customerName)
                InfoRow("방문 일정", visit.schedule)
                InfoRow("주소", visit.address)
                InfoRow("방문 ID", visit.visitId)
            }

            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        openDialer(
                            context = context,
                            phone = visit.phone
                        )
                    }
                ) {
                    Text("고객에게 전화")
                }

                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        openNavigation(
                            context = context,
                            address = visit.address
                        )
                    }
                ) {
                    Text("길찾기")
                }
            }

            SectionCard(
                title = "제품 및 증상"
            ) {
                InfoRow("제품", visit.productName)
                InfoRow("모델", visit.productCode)
                HorizontalDivider()
                Text(
                    text = visit.symptom,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold
                )
            }

            SectionCard(
                title = "고객 자가조치 결과"
            ) {
                Text(
                    text = visit.customerAction,
                    style = MaterialTheme.typography.bodyMedium
                )
            }

            SectionCard(
                title = "상담 요약"
            ) {
                Text(
                    text = visit.consultationSummary,
                    style = MaterialTheme.typography.bodyMedium
                )
            }

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
                        text = "AI 사전 점검 리포트",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color =
                            MaterialTheme.colorScheme.onPrimaryContainer
                    )

                    visit.priorityChecks.forEachIndexed { index, check ->
                        Text(
                            text = "${index + 1}. $check",
                            style = MaterialTheme.typography.bodyMedium,
                            color =
                                MaterialTheme.colorScheme.onPrimaryContainer
                        )
                    }

                    Surface(
                        color = MaterialTheme.colorScheme.surface,
                        shape = RoundedCornerShape(14.dp)
                    ) {
                        Column(
                            modifier = Modifier.padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            Text(
                                text = "공식 근거",
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = visit.officialEvidence,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                }
            }

            if (!visitStarted) {
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        visitStarted = true
                    }
                ) {
                    Text("방문 시작")
                }

                Text(
                    text = "방문 시작 후 점검 결과를 등록할 수 있습니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                Surface(
                    color = MaterialTheme.colorScheme.tertiaryContainer,
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Text(
                        text = "점검 진행 중 · 방문 결과를 등록해 주세요.",
                        modifier = Modifier.padding(14.dp),
                        color = MaterialTheme.colorScheme.onTertiaryContainer,
                        fontWeight = FontWeight.Bold
                    )
                }

                Button(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = onRegisterResult
                ) {
                    Text("방문 결과 등록")
                }
            }

            Spacer(Modifier.height(6.dp))
        }
    }
}

@Composable
private fun VisitStatusHeader(
    visit: TechnicianVisit,
    visitStarted: Boolean
) {
    Card(
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp)
        ) {
            Text(
                text = if (visitStarted) {
                    "점검 진행 중"
                } else {
                    visit.status.label
                },
                color = MaterialTheme.colorScheme.primary,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "${visit.schedule} · ${visit.customerName}",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.ExtraBold
            )
            Text(
                text = "현재 위치에서 약 ${visit.distanceKm}km",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun SectionCard(
    title: String,
    content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit
) {
    Card(
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = 1.dp
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            content()
        }
    }
}

@Composable
private fun InfoRow(
    label: String,
    value: String
) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(3.dp)
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium
        )
    }
}

private fun openDialer(
    context: Context,
    phone: String
) {
    val intent = Intent(
        Intent.ACTION_DIAL,
        Uri.parse("tel:$phone")
    )
    context.startActivity(intent)
}

private fun openNavigation(
    context: Context,
    address: String
) {
    val geoUri = Uri.parse(
        "geo:0,0?q=${Uri.encode(address)}"
    )
    val intent = Intent(
        Intent.ACTION_VIEW,
        geoUri
    )
    context.startActivity(
        Intent.createChooser(
            intent,
            "길찾기 앱 선택"
        )
    )
}
