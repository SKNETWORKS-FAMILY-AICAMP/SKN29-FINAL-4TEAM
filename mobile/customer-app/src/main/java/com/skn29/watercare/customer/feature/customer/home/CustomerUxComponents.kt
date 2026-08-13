package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPanel
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.math.roundToInt

@Composable
fun CustomerPriorityCtaCard(
    home: CustomerHomeData,
    intakeAvailable: Boolean,
    onStartIntake: (String) -> Unit,
    onOpenInquiry: (String) -> Unit,
) {
    val activeInquiry = home.activeInquiry

    LiquidGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("customerPriorityCta"),
        strong = true,
    ) {
        Text(
            if (activeInquiry == null) {
                "정수기에 문제가 있으신가요?"
            } else {
                "처리 중인 문의가 있어요"
            },
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Black,
        )

        Text(
            if (activeInquiry == null) {
                "증상을 알려주시면 필요한 안내를 도와드릴게요."
            } else {
                customerHomeStatusText(activeInquiry.statusCode)
            },
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        LiquidGlassButton(
            text = if (activeInquiry == null) {
                "증상 접수하기"
            } else {
                "진행 상황 확인"
            },
            onClick = {
                if (activeInquiry == null) {
                    onStartIntake(home.subscriptionId)
                } else {
                    onOpenInquiry(activeInquiry.inquiryId)
                }
            },
            enabled = activeInquiry != null || intakeAvailable,
            accent = true,
            modifier = Modifier
                .fillMaxWidth()
                .testTag(
                    if (activeInquiry == null) {
                        "priorityStartIntake"
                    } else {
                        "priorityOpenInquiry"
                    }
                ),
        )

        if (activeInquiry == null && !intakeAvailable) {
            Text(
                "현재 선택한 제품에서는 증상 접수를 시작할 수 없어요.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
fun CustomerFilterUsageCard(
    home: CustomerHomeData,
) {
    val estimate = estimateFilterUsage(home)

    LiquidGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("filterUsageEstimate"),
        strong = false,
    ) {
        Text(
            "필터 관리 상태",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Black,
        )

        if (estimate == null) {
            Text(
                "필터 사용 상태를 계산할 수 있는 관리 일정이 아직 없어요.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            home.startedOn
                ?.takeIf(String::isNotBlank)
                ?.let {
                    Text(
                        "구독 시작일 $it",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            return@LiquidGlassPanel
        }

        Column(
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                if (estimate.percent >= 100) {
                    "필터 교체 시점을 확인해주세요"
                } else {
                    "필터 예상 사용률 약 ${estimate.percent}%"
                },
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.ExtraBold,
            )

            LinearProgressIndicator(
                progress = { estimate.progress },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp),
            )

            Text(
                when {
                    estimate.remainingDays > 0 ->
                        "다음 관리까지 약 ${estimate.remainingDays}일 남았어요."
                    estimate.remainingDays == 0L ->
                        "오늘이 다음 관리 예정일이에요."
                    else ->
                        "다음 관리 예정일이 지났어요."
                },
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Text(
                "${estimate.basisLabel} · 날짜 기준 예상값",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private data class FilterUsageEstimate(
    val percent: Int,
    val progress: Float,
    val remainingDays: Long,
    val basisLabel: String,
)

private fun estimateFilterUsage(
    home: CustomerHomeData,
    today: LocalDate = LocalDate.now(),
): FilterUsageEstimate? {
    val lastCare = parseCustomerDate(home.lastCareOn)
    val started = parseCustomerDate(home.startedOn)
    val nextCare = parseCustomerDate(home.nextCareOn)

    val baseDate = lastCare ?: started ?: return null
    val endDate = nextCare ?: return null

    val totalDays = ChronoUnit.DAYS.between(
        baseDate,
        endDate,
    )

    if (totalDays <= 0L) return null

    val elapsedDays = ChronoUnit.DAYS.between(
        baseDate,
        today,
    ).coerceAtLeast(0L)

    val rawProgress = elapsedDays.toDouble() / totalDays.toDouble()
    val progress = rawProgress
        .coerceIn(0.0, 1.0)
        .toFloat()

    val percent = (progress * 100f)
        .roundToInt()
        .coerceIn(0, 100)

    val remainingDays = ChronoUnit.DAYS.between(
        today,
        endDate,
    )

    return FilterUsageEstimate(
        percent = percent,
        progress = progress,
        remainingDays = remainingDays,
        basisLabel = if (lastCare != null) {
            "최근 관리일 기준"
        } else {
            "구독 시작일 기준"
        },
    )
}

private fun parseCustomerDate(
    value: String?,
): LocalDate? {
    val normalized = value
        ?.trim()
        ?.takeIf(String::isNotEmpty)
        ?.take(10)
        ?: return null

    return runCatching {
        LocalDate.parse(normalized)
    }.getOrNull()
}

private fun customerHomeStatusText(
    statusCode: String,
): String = when (statusCode.trim().uppercase()) {
    "DRAFT" -> "접수 내용을 확인하고 있어요."
    "QUESTIONNAIRE_IN_PROGRESS" -> "증상을 조금 더 확인하고 있어요."
    "AI_GUIDANCE" -> "문제 해결 안내가 준비됐어요."
    "CONSULTATION_REQUIRED" -> "상담이 필요해요."
    "CONSULTATION_IN_PROGRESS" -> "상담을 진행하고 있어요."
    "VISIT_REVIEW_PENDING" -> "방문 점검이 필요한지 확인하고 있어요."
    "VISIT_SCHEDULING" -> "방문 일정을 조율하고 있어요."
    "VISIT_SCHEDULED" -> "방문 일정이 잡혔어요."
    "COMPLETION_PENDING" -> "처리 결과를 확인하고 있어요."
    "REVISIT_REQUIRED" -> "추가 방문 점검이 필요해요."
    "REOPENED" -> "문의 내용을 다시 확인하고 있어요."
    "RESOLVED" -> "처리가 완료됐어요."
    "CANCELLED" -> "접수가 취소됐어요."
    else -> "현재 문의 진행 상황을 확인해보세요."
}