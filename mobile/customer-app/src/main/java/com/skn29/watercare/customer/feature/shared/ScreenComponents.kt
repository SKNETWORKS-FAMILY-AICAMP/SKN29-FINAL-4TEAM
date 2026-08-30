@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.customer.feature.shared

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.DataClassification
import com.skn29.watercare.core.model.EvidenceCardData
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.ProductSummary
import com.skn29.watercare.core.model.RiskLevel
import com.skn29.watercare.core.model.UsageGuidanceStatus
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPanel
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.core.ui.components.LiquidGlassTone
import com.skn29.watercare.core.ui.components.LiquidGlassToneProvider
import com.skn29.watercare.core.ui.components.WaterBridgeCustomerPalette
import com.skn29.watercare.core.ui.components.ReferencePearlBackground
import com.skn29.watercare.core.ui.theme.WaterCaution
import com.skn29.watercare.core.ui.theme.WaterDanger
import com.skn29.watercare.core.ui.theme.WaterGeneral
import com.skn29.watercare.customer.R
import com.skn29.watercare.core.ui.theme.WaterSubText
import com.skn29.watercare.core.ui.theme.WaterTokens

@Composable
fun WaterCareScreen(
    title: String,
    onBack: (() -> Unit)? = null,
    bottomBar: @Composable () -> Unit = {},
    content: @Composable ColumnScope.() -> Unit,
) {
    LiquidGlassToneProvider(
        tone = LiquidGlassTone.CUSTOMER,
    ) {
        WaterCareScreenBody(
            title = title,
            onBack = onBack,
            bottomBar = bottomBar,
            content = content,
        )
    }
}

@Composable
private fun WaterCareScreenBody(
    title: String,
    onBack: (() -> Unit)? = null,
    bottomBar: @Composable () -> Unit = {},
    content: @Composable ColumnScope.() -> Unit,
) {
    ReferencePearlBackground(
        palette = WaterBridgeCustomerPalette,
        backgroundRes = R.drawable.water_splash_customer_r19,
        imageAlpha = 0.16f,
    ) {
        Scaffold(
            containerColor = Color.Transparent,
            bottomBar = bottomBar,
            topBar = {
                TopAppBar(
                    title = {
                        Text(
                            title,
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.ExtraBold,
                        )
                    },
                    navigationIcon = {
                        if (onBack != null) {
                            LiquidGlassButton(
                                text = "뒤로",
                                leadingIcon = "‹",
                                onClick = onBack,
                                compact = true,
                                modifier = Modifier.heightIn(min = 48.dp),
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.Transparent,
                        scrolledContainerColor = Color.White.copy(alpha = 0.94f),
                    ),
                )
            },
        ) { padding ->
            Box(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .padding(padding),
                contentAlignment =
                    Alignment.TopCenter,
            ) {
                Column(
                    modifier =
                        Modifier
                            .widthIn(max = 960.dp)
                            .fillMaxWidth()
                            .verticalScroll(
                                rememberScrollState()
                            )
                            .padding(18.dp),
                    verticalArrangement =
                        Arrangement.spacedBy(
                            WaterTokens.SpaceMd,
                        ),
                    content = content,
                )
            }
        }
    }
}

@Composable
fun SectionCard(
    title: String,
    isDanger: Boolean = false,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    LiquidGlassPanel(
        modifier = modifier.fillMaxWidth(),
        danger = isDanger,
    ) {
        Text(
            title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.ExtraBold,
            color = if (isDanger) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        )
        content()
    }
}

@Composable
fun ProductInfoCard(
    product: ProductSummary,
    questionnaireStatus: String,
    nextCareOn: String,
) {
    LiquidGlassPanel(strong = true) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            LiquidGlassPill(product.managementTypeLabel)
        }
        Text(
            "사용 중인 정수기",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        LiquidGlassPanel(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(14.dp),
        ) {
            Text(
                "현재 정수기 정보",
                fontWeight = FontWeight.ExtraBold,
            )
            Text("다음 관리 · $nextCareOn")
        }
    }
}

@Composable
fun StatusBadge(
    risk: RiskLevel,
    usage: UsageGuidanceStatus,
) {
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
        UsageGuidanceStatus.PENDING_CONSULTATION,
        UsageGuidanceStatus.UNKNOWN -> "상담 확인 필요"
    }

    val color = when (risk) {
        RiskLevel.GENERAL -> WaterGeneral
        RiskLevel.CAUTION -> WaterCaution
        RiskLevel.DANGER -> WaterDanger
        RiskLevel.UNKNOWN -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    LiquidGlassPill(
        text = "$riskText · $usageText",
        tint = color,
    )
}

@Composable
fun EvidenceCard(evidence: EvidenceCardData) {
    LiquidGlassPanel(
        modifier = Modifier.fillMaxWidth(),
        strong = true,
    ) {
        val classification = when (
            evidence.dataClassification.lowercase()
        ) {
            "official" -> DataClassification.OFFICIAL
            "team_designed" -> DataClassification.TEAM_DESIGNED
            "synthetic" -> DataClassification.SYNTHETIC
            else -> DataClassification.UNKNOWN
        }

        LiquidGlassPill(
            when (classification) {
                DataClassification.OFFICIAL -> "공식 안내 자료"
                DataClassification.TEAM_DESIGNED -> "서비스 안내 자료"
                DataClassification.SYNTHETIC -> "예시 안내 자료"
                DataClassification.UNKNOWN -> "안내 자료"
            }
        )
        Text(
            evidence.documentName,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.ExtraBold,
        )
        Text(evidence.structuredSummary)

        val officialUrl = evidence.officialUrl
        if (!officialUrl.isNullOrBlank()) {
            val uriHandler = LocalUriHandler.current
            LiquidGlassButton(
                text = "공식 안내 확인",
                onClick = { uriHandler.openUri(officialUrl) },
                accent = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
fun BulletList(
    items: List<String>,
    emptyText: String = "해당 항목이 없습니다.",
) {
    if (items.isEmpty()) {
        Text(
            emptyText,
            color = WaterSubText,
        )
    } else {
        items.forEach { item ->
            Text("• $item")
        }
    }
}

@Composable
fun WorkflowActionButton(
    action: AllowedAction,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    when (action.normalizedCode) {
        InquiryActionLabels.REQUEST_CONSULTATION -> LiquidGlassButton(
            text = action.displayLabel,
            onClick = onClick,
            enabled = enabled,
            accent = true,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("requestConsultation"),
        )

        InquiryActionLabels.CANCEL_INQUIRY -> LiquidGlassButton(
            text = action.displayLabel,
            onClick = onClick,
            enabled = enabled,
            accent = false,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("cancelInquiry"),
        )

        else -> Unit
    }
}

@Composable
fun SpacerSmall() = Spacer(
    Modifier.height(WaterTokens.SpaceXs)
)
