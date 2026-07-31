@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.customer.feature.shared

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.model.DataClassification
import com.skn29.watercare.core.model.EvidenceCardData
import com.skn29.watercare.core.model.ProductSummary
import com.skn29.watercare.core.model.RiskLevel
import com.skn29.watercare.core.model.UsageGuidanceStatus
import com.skn29.watercare.core.ui.theme.WaterDanger
import com.skn29.watercare.core.ui.theme.WaterOrange
import com.skn29.watercare.core.ui.theme.WaterSubText
import com.skn29.watercare.core.ui.theme.WaterSuccess

@Composable
fun WaterCareScreen(
    title: String,
    onBack: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = { Text(title, fontWeight = FontWeight.ExtraBold) },
                navigationIcon = {
                    if (onBack != null) TextButton(onClick = onBack) { Text("뒤로") }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
            content = content,
        )
    }
}

@Composable
fun SectionCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
            content()
        }
    }
}

@Composable
fun ProductInfoCard(product: ProductSummary, questionnaireStatus: String, nextCareOn: String) {
    Card(
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (product.isSynthetic) AssistChip(onClick = {}, label = { Text("합성 데이터") })
                AssistChip(onClick = {}, label = { Text(product.managementTypeLabel) })
            }
            Text(product.modelCode, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
            Text(product.modelName, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Surface(shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.secondaryContainer) {
                Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text("현재 정수기 정보", fontWeight = FontWeight.Bold)
                    Text("식별번호 ${product.serialNo}", color = WaterSubText)
                    Text("문진 상태 · $questionnaireStatus")
                    Text("다음 관리 · $nextCareOn")
                }
            }
        }
    }
}

@Composable
fun StatusBadge(risk: RiskLevel, usage: UsageGuidanceStatus) {
    val riskText = when (risk) {
        RiskLevel.GENERAL -> "일반"
        RiskLevel.CAUTION -> "주의"
        RiskLevel.DANGER -> "위험"
        RiskLevel.UNKNOWN -> "판단 보류"
    }
    val usageText = when (usage) {
        UsageGuidanceStatus.NORMAL -> "정상 사용"
        UsageGuidanceStatus.PARTIAL_STOP -> "일부 기능 중지"
        UsageGuidanceStatus.TOTAL_STOP -> "전체 사용 중지"
        UsageGuidanceStatus.PENDING_CONSULTATION, UsageGuidanceStatus.UNKNOWN -> "상담 확인 필요"
    }
    val color = when (risk) {
        RiskLevel.DANGER -> WaterDanger
        RiskLevel.CAUTION -> WaterOrange
        RiskLevel.GENERAL -> WaterSuccess
        RiskLevel.UNKNOWN -> MaterialTheme.colorScheme.primary
    }
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = color.copy(alpha = 0.13f),
    ) {
        Text(
            "$riskText · $usageText",
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            color = color,
            fontWeight = FontWeight.ExtraBold,
        )
    }
}

@Composable
fun EvidenceCard(evidence: EvidenceCardData) {
    Card(
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            val classification = when (evidence.dataClassification.lowercase()) {
                "official" -> DataClassification.OFFICIAL
                "team_designed" -> DataClassification.TEAM_DESIGNED
                "synthetic" -> DataClassification.SYNTHETIC
                else -> DataClassification.UNKNOWN
            }
            Text(
                when (classification) {
                    DataClassification.OFFICIAL -> "공식 근거"
                    DataClassification.TEAM_DESIGNED -> "팀 설계 자료"
                    DataClassification.SYNTHETIC -> "합성 검증 자료"
                    DataClassification.UNKNOWN -> "분류 확인 필요"
                },
                fontWeight = FontWeight.ExtraBold,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(evidence.documentName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("버전 ${evidence.version}${evidence.page?.let { " · ${it}쪽" }.orEmpty()}")
            Text(evidence.structuredSummary)
            Text("검증 상태 · ${evidence.verificationStatus}", style = MaterialTheme.typography.bodySmall)
            val officialUrl = evidence.officialUrl
            if (!officialUrl.isNullOrBlank()) {
                val uriHandler = LocalUriHandler.current
                OutlinedButton(onClick = { uriHandler.openUri(officialUrl) }) { Text("공식 문서 열기") }
            }
        }
    }
}

@Composable
fun BulletList(items: List<String>, emptyText: String = "해당 항목이 없습니다.") {
    if (items.isEmpty()) Text(emptyText, color = WaterSubText)
    else items.forEach { Text("• $it") }
}

@Composable
fun WorkflowActionButton(action: String, enabled: Boolean = true, onClick: () -> Unit) {
    when (action.uppercase()) {
        "REQUEST_CONSULTATION" -> Button(
            onClick = onClick,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = WaterOrange),
        ) { Text("상담 요청") }
        "CONFIRM_GUIDANCE" -> OutlinedButton(
            onClick = onClick,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("안내 확인") }
        "MARK_RESOLVED", "RESOLVE" -> OutlinedButton(
            onClick = onClick,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth().testTag("resolvedAction"),
        ) { Text("증상 해결됨") }
        else -> Unit
    }
}

@Composable
fun SpacerSmall() = Spacer(Modifier.height(4.dp))
