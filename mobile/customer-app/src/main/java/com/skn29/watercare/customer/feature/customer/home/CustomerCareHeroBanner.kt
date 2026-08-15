package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceGlassPanel
import com.skn29.watercare.customer.R
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.math.roundToInt

@Composable
fun CustomerCareHeroBanner(
    home: CustomerHomeData,
    activeInquiryId: String? = home.activeInquiry?.inquiryId,
    activeInquiryStatusCode: String? = home.activeInquiry?.statusCode,
    intakeAvailable: Boolean,
    intakeUnavailableReason: String?,
    onStartIntake: (String) -> Unit,
    onOpenInquiry: (String) -> Unit,
) {
    val palette = CustomerReferencePalette
    val estimate = calculateFilterUsageEstimate(home)
    val hasActiveInquiry = !activeInquiryId.isNullOrBlank()

    val infiniteTransition =
        rememberInfiniteTransition(
            label = "customerPurifierMotion"
        )

    val floatingY by infiniteTransition.animateFloat(
        initialValue = -4f,
        targetValue = 6f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2200),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "customerPurifierFloat",
    )

    val floatingScale by infiniteTransition.animateFloat(
        initialValue = 0.985f,
        targetValue = 1.025f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 2600),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "customerPurifierScale",
    )

    val targetProgress = estimate?.progress ?: 0f

    val animatedProgress by animateFloatAsState(
        targetValue = targetProgress,
        animationSpec = tween(durationMillis = 1100),
        label = "filterUsageProgress",
    )

    ReferenceGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("customerCareHeroBanner"),
        palette = palette,
        strong = true,
    ) {
        Text(
            "우리 집 정수기",
            style = MaterialTheme.typography.labelLarge,
            color = palette.accent,
            fontWeight = FontWeight.ExtraBold,
        )

        Text(
            "필터 관리 상태",
            style = MaterialTheme.typography.headlineSmall,
            color = palette.textStrong,
            fontWeight = FontWeight.Black,
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FilterCircularProgress(
                percent = estimate?.percent,
                animatedProgress = animatedProgress,
                modifier = Modifier.size(128.dp),
            )

            Box(
                modifier = Modifier.size(148.dp),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(
                        R.drawable.dashboard_purifier
                    ),
                    contentDescription = "사용 중인 정수기",
                    modifier = Modifier
                        .size(138.dp)
                        .offset(y = floatingY.dp)
                        .scale(floatingScale),
                    contentScale = ContentScale.Fit,
                )
            }
        }

        Text(
            managementHeadline(estimate),
            style = MaterialTheme.typography.titleLarge,
            color = palette.textStrong,
            fontWeight = FontWeight.Black,
        )

        Text(
            managementMessage(estimate),
            color = palette.textMuted,
            style = MaterialTheme.typography.bodyLarge,
        )

        estimate?.let {
            Text(
                "${it.basisLabel} · 날짜 기준 예상값",
                color = palette.textMuted,
                style = MaterialTheme.typography.bodySmall,
            )
        }

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            if (!hasActiveInquiry) {
                "정수기에 불편한 점이 있으신가요?"
            } else {
                "처리 중인 문의가 있어요"
            },
            style = MaterialTheme.typography.titleMedium,
            color = palette.textStrong,
            fontWeight = FontWeight.ExtraBold,
        )

        Text(
            if (!hasActiveInquiry) {
                "증상을 선택하면 필요한 확인을 바로 시작할게요."
            } else {
                customerHeroInquiryStatus(
                    activeInquiryStatusCode.orEmpty()
                )
            },
            color = palette.textMuted,
            style = MaterialTheme.typography.bodyMedium,
        )

        ReferenceGlassButton(
            text = if (!hasActiveInquiry) {
                "증상 접수하기"
            } else {
                "진행 상황 확인"
            },
            palette = palette,
            accent = true,
            enabled =
                hasActiveInquiry ||
                    intakeAvailable,
            onClick = {
                if (!hasActiveInquiry) {
                    onStartIntake(home.subscriptionId)
                } else {
                    onOpenInquiry(requireNotNull(activeInquiryId))
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .testTag(
                    if (!hasActiveInquiry) {
                        "heroStartIntake"
                    } else {
                        "heroOpenInquiry"
                    }
                ),
        )

        if (
            !hasActiveInquiry &&
            !intakeAvailable
        ) {
            Text(
                customerIntakeUnavailableMessage(
                    intakeUnavailableReason
                ),
                color = palette.textMuted,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun FilterCircularProgress(
    percent: Int?,
    animatedProgress: Float,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette
    val trackColor =
        MaterialTheme.colorScheme.surfaceVariant
            .copy(alpha = 0.70f)
    val progressColor = palette.accent

    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center,
    ) {
        Canvas(
            modifier = Modifier.fillMaxSize(),
        ) {
            val stroke = 12.dp.toPx()
            val inset = stroke / 2f
            val arcSize = Size(
                width = size.width - stroke,
                height = size.height - stroke,
            )

            drawArc(
                color = trackColor,
                startAngle = -90f,
                sweepAngle = 360f,
                useCenter = false,
                topLeft = Offset(inset, inset),
                size = arcSize,
                style = Stroke(
                    width = stroke,
                    cap = StrokeCap.Round,
                ),
            )

            drawArc(
                color = progressColor,
                startAngle = -90f,
                sweepAngle =
                    360f *
                        animatedProgress.coerceIn(
                            0f,
                            1f,
                        ),
                useCenter = false,
                topLeft = Offset(inset, inset),
                size = arcSize,
                style = Stroke(
                    width = stroke,
                    cap = StrokeCap.Round,
                ),
            )
        }

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                if (percent == null) {
                    "--"
                } else {
                    "$percent%"
                },
                style = MaterialTheme.typography.headlineMedium,
                color = palette.textStrong,
                fontWeight = FontWeight.Black,
            )

            Text(
                "예상 사용",
                style = MaterialTheme.typography.labelMedium,
                color = palette.textMuted,
            )
        }
    }
}

private data class CustomerFilterEstimate(
    val percent: Int,
    val progress: Float,
    val remainingDays: Long,
    val basisLabel: String,
)

private fun calculateFilterUsageEstimate(
    home: CustomerHomeData,
    today: LocalDate = LocalDate.now(),
): CustomerFilterEstimate? {
    val lastCare =
        parseCustomerHeroDate(home.lastCareOn)
    val started =
        parseCustomerHeroDate(home.startedOn)
    val nextCare =
        parseCustomerHeroDate(home.nextCareOn)

    val baseDate =
        lastCare ?: started ?: return null
    val endDate =
        nextCare ?: return null

    val totalDays =
        ChronoUnit.DAYS.between(
            baseDate,
            endDate,
        )

    if (totalDays <= 0L) {
        return null
    }

    val elapsedDays =
        ChronoUnit.DAYS.between(
            baseDate,
            today,
        ).coerceAtLeast(0L)

    val rawProgress =
        elapsedDays.toDouble() /
            totalDays.toDouble()

    val progress =
        rawProgress
            .coerceIn(0.0, 1.0)
            .toFloat()

    return CustomerFilterEstimate(
        percent =
            (progress * 100f)
                .roundToInt()
                .coerceIn(0, 100),
        progress = progress,
        remainingDays =
            ChronoUnit.DAYS.between(
                today,
                endDate,
            ),
        basisLabel =
            if (lastCare != null) {
                "최근 관리일 기준"
            } else {
                "구독 시작일 기준"
            },
    )
}

private fun parseCustomerHeroDate(
    value: String?,
): LocalDate? {
    val normalized =
        value
            ?.trim()
            ?.takeIf(String::isNotEmpty)
            ?.take(10)
            ?: return null

    return runCatching {
        LocalDate.parse(normalized)
    }.getOrNull()
}

private fun managementHeadline(
    estimate: CustomerFilterEstimate?,
): String = when {
    estimate == null ->
        "관리 일정을 확인하고 있어요"

    estimate.percent >= 100 ->
        "필터 교체 시점을 확인해주세요"

    estimate.percent >= 80 ->
        "필터 교체 시점이 가까워지고 있어요"

    else ->
        "필터 상태는 아직 여유가 있어요"
}

private fun managementMessage(
    estimate: CustomerFilterEstimate?,
): String = when {
    estimate == null ->
        "관리 일정이 준비되면 여기에서 바로 알려드릴게요."

    estimate.remainingDays > 0 ->
        "다음 관리까지 약 ${estimate.remainingDays}일 남았어요."

    estimate.remainingDays == 0L ->
        "오늘이 다음 관리 예정일이에요."

    else ->
        "다음 관리 예정일이 지났어요."
}

private fun customerHeroInquiryStatus(
    statusCode: String,
): String = when (
    statusCode.trim().uppercase()
) {
    "DRAFT" ->
        "접수 내용을 확인하고 있어요."

    "QUESTIONNAIRE_IN_PROGRESS" ->
        "증상을 조금 더 확인하고 있어요."

    "AI_GUIDANCE" ->
        "문제 해결 안내가 준비됐어요."

    "CONSULTATION_REQUIRED" ->
        "상담이 필요해요."

    "CONSULTATION_IN_PROGRESS" ->
        "상담을 진행하고 있어요."

    "VISIT_REVIEW_PENDING" ->
        "방문 점검이 필요한지 확인하고 있어요."

    "VISIT_SCHEDULING" ->
        "방문 일정을 조율하고 있어요."

    "VISIT_SCHEDULED" ->
        "방문 일정이 잡혔어요."

    "COMPLETION_PENDING" ->
        "처리 결과를 확인하고 있어요."

    "REVISIT_REQUIRED" ->
        "추가 방문 점검이 필요해요."

    "REOPENED" ->
        "문의 내용을 다시 확인하고 있어요."

    "RESOLVED" ->
        "처리가 완료됐어요."

    "CANCELLED" ->
        "접수가 취소됐어요."

    else ->
        "현재 문의 진행 상황을 확인해보세요."
}

private fun customerIntakeUnavailableMessage(
    reason: String?,
): String = when {
    reason.isNullOrBlank() ->
        "현재 증상 접수를 시작할 수 없어요."

    reason.contains(
        "활성 구독",
        ignoreCase = true,
    ) ->
        "현재 이용 중인 제품에서만 증상 접수를 시작할 수 있어요."

    reason.contains(
        "WPUJAC104DWH",
        ignoreCase = true,
    ) ||
        reason.contains(
            "P0",
            ignoreCase = true,
        ) ->
        "현재 선택된 제품에서는 증상 접수를 이용할 수 없어요."

    reason.contains(
        "Backend",
        ignoreCase = true,
    ) ||
        reason.contains(
            "API",
            ignoreCase = true,
        ) ||
        reason.contains(
            "Remote",
            ignoreCase = true,
        ) ||
        reason.contains(
            "Fixture",
            ignoreCase = true,
        ) ||
        reason.contains(
            "Mock",
            ignoreCase = true,
        ) ->
        "현재 증상 접수를 이용할 수 없어요. 잠시 후 다시 시도해주세요."

    else ->
        reason
}
@Composable
fun CustomerProductInfoCard(
    home: CustomerHomeData,
) {
    val palette = CustomerReferencePalette

    ReferenceGlassPanel(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("customerProductInfo"),
        palette = palette,
        strong = false,
    ) {
        Text(
            "내 정수기 상태",
            style = MaterialTheme.typography.titleLarge,
            color = palette.textStrong,
            fontWeight = FontWeight.Black,
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Image(
                painter = painterResource(
                    R.drawable.dashboard_purifier
                ),
                contentDescription = "내 정수기 제품",
                modifier = Modifier.size(92.dp),
                contentScale = ContentScale.Fit,
            )

            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    home.product.modelName,
                    style = MaterialTheme.typography.titleMedium,
                    color = palette.textStrong,
                    fontWeight = FontWeight.ExtraBold,
                )

                Text(
                    "모델 ${home.product.modelCode}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = palette.textMuted,
                )

                Text(
                    home.product.managementTypeLabel,
                    style = MaterialTheme.typography.bodyMedium,
                    color = palette.textMuted,
                )

                if (
                    home.nextCareOn.isNotBlank() &&
                    home.nextCareOn != "미정"
                ) {
                    Text(
                        "다음 관리 ${home.nextCareOn}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = palette.textMuted,
                    )
                }
            }
        }
    }
}