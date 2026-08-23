package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.ui.graphics.Color
import kotlin.math.sin
import kotlin.math.cos
import androidx.compose.animation.core.LinearEasing
// WaterCare V5.5 motion
// WaterCare V5.6 showcase motion
// WaterCare V5.7 showcase max
// WaterCare V5.8.2 interactive motion

import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.animation.togetherWith
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.fadeOut
import androidx.compose.animation.fadeIn
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.isP0SupportedActiveSubscription
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.customer.R
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.math.roundToInt

@Composable
fun CustomerVisualProductHero(
    home: CustomerHomeData,
    displayModel: CustomerModelVisualSpec =
        customerModelVisualSpec(
            home.product.modelCode,
            home.product.modelName,
        ),
    previewMode: Boolean = false,
    canChangeProduct: Boolean,
    onChangeProduct: () -> Unit,
    activeInquiryId: String? = null,
    activeInquiryStatusCode: String? = null,
    intakeAvailable: Boolean = false,
    intakeUnavailableReason: String? = null,
    onStartIntake: (String) -> Unit = {},
    onOpenInquiry: (String) -> Unit = {},
    onOpenCare: () -> Unit = {},
) {
    val palette = CustomerReferencePalette
    val filter =
        if (previewMode) {
            null
        } else {
            calculateRemainingFilterEstimate(home)
        }

    val animatedProgress by animateFloatAsState(
        targetValue = filter?.progress ?: 0f,
        animationSpec = tween(
            durationMillis = 760,
        ),
        label = "finalDashboardFilterProgress",
    )

    val filterGaugeColor = when {
        filter == null ->
            displayModel.accent
        filter.percent <= 20 ->
            MaterialTheme.colorScheme.error
        filter.percent <= 40 ->
            MaterialTheme.colorScheme.tertiary
        else ->
            displayModel.accent
    }

    val filterStateLabel = when {
        filter == null ->
            "확인 중"
        filter.percent <= 20 ->
            "교체 확인"
        filter.percent <= 40 ->
            "교체 준비"
        else ->
            "양호"
    }

    val nextCareLabel =
        if (previewMode) {
            "미리보기"
        } else {
            careDday(home.nextCareOn)
        }

    val hasActiveInquiry =
        !activeInquiryId.isNullOrBlank()

    CustomerCleanCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("customerCareHeroBanner"),
        contentPadding = PaddingValues(
            horizontal = 16.dp,
            vertical = 15.dp,
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement =
                Arrangement.SpaceBetween,
            verticalAlignment =
                Alignment.CenterVertically,
        ) {
            Column(
                verticalArrangement =
                    Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = "내 정수기 상태",
                    style =
                        MaterialTheme.typography.titleLarge,
                    color = palette.textStrong,
                    fontWeight = FontWeight.Bold,
                )

                Text(
                    text = "필요한 상태만 한눈에 확인하세요.",
                    style =
                        MaterialTheme.typography.bodySmall,
                    color = palette.textMuted,
                )
            }

            if (canChangeProduct) {
                TextButton(
                    onClick = onChangeProduct,
                    modifier =
                        Modifier.testTag(
                            "changeSubscription"
                        ),
                ) {
                    Text(
                        text = "제품 변경 ›",
                        color = palette.accent,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }

        BoxWithConstraints(
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (maxWidth < 370.dp) {
                Column(
                    modifier =
                        Modifier.fillMaxWidth(),
                    horizontalAlignment =
                        Alignment.CenterHorizontally,
                    verticalArrangement =
                        Arrangement.spacedBy(12.dp),
                ) {
                    FinalDashboardPurifierGauge(
                        displayModel = displayModel,
                        previewMode = previewMode,
                        progress = animatedProgress,
                        filterPercent = filter?.percent,
                        filterColor = filterGaugeColor,
                        modifier = Modifier.size(190.dp),
                    )

                    FinalDashboardFilterSummary(
                        previewMode = previewMode,
                        filterPercent = filter?.percent,
                        filterStateLabel = filterStateLabel,
                        nextCareLabel = nextCareLabel,
                        filterColor = filterGaugeColor,
                        onOpenCare = onOpenCare,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            } else {
                Row(
                    modifier =
                        Modifier.fillMaxWidth(),
                    horizontalArrangement =
                        Arrangement.spacedBy(16.dp),
                    verticalAlignment =
                        Alignment.CenterVertically,
                ) {
                    FinalDashboardPurifierGauge(
                        displayModel = displayModel,
                        previewMode = previewMode,
                        progress = animatedProgress,
                        filterPercent = filter?.percent,
                        filterColor = filterGaugeColor,
                        modifier = Modifier
                            .weight(1f)
                            .height(206.dp),
                    )

                    FinalDashboardFilterSummary(
                        previewMode = previewMode,
                        filterPercent = filter?.percent,
                        filterStateLabel = filterStateLabel,
                        nextCareLabel = nextCareLabel,
                        filterColor = filterGaugeColor,
                        onOpenCare = onOpenCare,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }

        FinalDashboardProblemCheck(
            home = home,
            activeInquiryId = activeInquiryId,
            activeInquiryStatusCode =
                activeInquiryStatusCode,
            intakeAvailable = intakeAvailable,
            intakeUnavailableReason =
                intakeUnavailableReason,
            previewMode = previewMode,
            hasActiveInquiry =
                hasActiveInquiry,
            onStartIntake = onStartIntake,
            onOpenInquiry = onOpenInquiry,
        )
    }
}

@Composable
private fun FinalDashboardPurifierGauge(
    displayModel: CustomerModelVisualSpec,
    previewMode: Boolean,
    progress: Float,
    filterPercent: Int?,
    filterColor: Color,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette

    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center,
    ) {
        FilterRemainingRing(
            progress = progress,
            accentColor = filterColor,
            trackColor =
                displayModel.softAccent.copy(
                    alpha = 0.42f
                ),
            modifier = Modifier.fillMaxSize(),
        )

        CustomerModelMascot(
            model = displayModel,
            modifier = Modifier.size(110.dp),
        )

        if (
            !previewMode &&
            filterPercent != null
        ) {
            Box(
                modifier = Modifier
                    .align(
                        Alignment.BottomCenter
                    )
                    .clip(
                        RoundedCornerShape(
                            999.dp
                        )
                    )
                    .background(
                        Color.White.copy(
                            alpha = 0.94f
                        )
                    )
                    .padding(
                        horizontal = 12.dp,
                        vertical = 6.dp,
                    ),
            ) {
                Text(
                    text =
                        "필터 ${filterPercent}%",
                    style =
                        MaterialTheme.typography
                            .labelLarge,
                    color = palette.textStrong,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

@Composable
private fun FinalDashboardFilterSummary(
    previewMode: Boolean,
    filterPercent: Int?,
    filterStateLabel: String,
    nextCareLabel: String,
    filterColor: Color,
    onOpenCare: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette

    Column(
        modifier = modifier,
        horizontalAlignment =
            Alignment.Start,
        verticalArrangement =
            Arrangement.spacedBy(7.dp),
    ) {
        Text(
            text = "필터 상태",
            style =
                MaterialTheme.typography
                    .labelLarge,
            color = palette.textMuted,
        )

        Row(
            horizontalArrangement =
                Arrangement.spacedBy(7.dp),
            verticalAlignment =
                Alignment.CenterVertically,
        ) {
            Text(
                text =
                    if (previewMode) {
                        "미리보기"
                    } else {
                        filterStateLabel
                    },
                style =
                    MaterialTheme.typography
                        .titleLarge,
                color =
                    if (previewMode) {
                        palette.textStrong
                    } else {
                        filterColor
                    },
                fontWeight = FontWeight.Bold,
            )

            if (!previewMode) {
                Text(
                    text = "✓",
                    style =
                        MaterialTheme.typography
                            .titleLarge,
                    color = filterColor,
                    fontWeight =
                        FontWeight.Black,
                )
            }
        }

        if (
            !previewMode &&
            filterPercent != null
        ) {
            Text(
                text =
                    "${filterPercent}%",
                style =
                    MaterialTheme.typography
                        .displaySmall,
                color = filterColor,
                fontWeight = FontWeight.Black,
            )
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(
                    RoundedCornerShape(14.dp)
                )
                .background(
                    palette.accentSoft.copy(
                        alpha = 0.18f
                    )
                )
                .padding(
                    horizontal = 11.dp,
                    vertical = 10.dp,
                ),
        ) {
            Column(
                verticalArrangement =
                    Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = "다음 관리까지",
                    style =
                        MaterialTheme.typography
                            .labelMedium,
                    color = palette.textMuted,
                )
                Text(
                    text = nextCareLabel,
                    style =
                        MaterialTheme.typography
                            .titleSmall,
                    color = palette.textStrong,
                    fontWeight =
                        FontWeight.Bold,
                )
            }
        }

        TextButton(
            onClick = onOpenCare,
            modifier =
                Modifier.testTag(
                    "openFilterCare"
                ),
        ) {
            Text(
                text = "필터 상태 자세히 보기 ›",
                color = palette.accent,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

@Composable
private fun FinalDashboardProblemCheck(
    home: CustomerHomeData,
    activeInquiryId: String?,
    activeInquiryStatusCode: String?,
    intakeAvailable: Boolean,
    intakeUnavailableReason: String?,
    previewMode: Boolean,
    hasActiveInquiry: Boolean,
    onStartIntake: (String) -> Unit,
    onOpenInquiry: (String) -> Unit,
) {
    val palette = CustomerReferencePalette

    val normalized =
        activeInquiryStatusCode
            ?.trim()
            ?.uppercase()
            .orEmpty()

    val title = when {
        previewMode ->
            "문제 확인하기"
        normalized == "DRAFT" ||
            normalized ==
                "QUESTIONNAIRE_IN_PROGRESS" ->
            "작성 중인 문진이 있어요"
        normalized == "AI_GUIDANCE" ->
            "해결 방법이 준비됐어요"
        hasActiveInquiry ->
            "진행 중인 요청이 있어요"
        else ->
            "문제 확인하기"
    }

    val subtitle = when {
        previewMode ->
            "실제 제품을 선택하면 이용할 수 있어요."
        normalized == "DRAFT" ||
            normalized ==
                "QUESTIONNAIRE_IN_PROGRESS" ->
            "작성하던 내용부터 이어서 진행하세요."
        normalized == "AI_GUIDANCE" ->
            "확인된 내용을 바탕으로 해결 방법을 확인해보세요."
        hasActiveInquiry ->
            inquiryStatusMessage(
                activeInquiryStatusCode.orEmpty()
            )
        intakeAvailable ->
            "물이 이상할 때 바로 확인하세요."
        else ->
            intakeUnavailableReason
                ?.takeIf { it.isNotBlank() }
                ?: "문제 확인 기능을 준비하고 있어요."
    }

    val actionText = when {
        normalized == "DRAFT" ||
            normalized ==
                "QUESTIONNAIRE_IN_PROGRESS" ->
            "이어서 작성"
        normalized == "AI_GUIDANCE" ->
            "해결 방법 보기"
        hasActiveInquiry ->
            "진행 상황 보기"
        else ->
            "문제 확인 시작"
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(
                RoundedCornerShape(18.dp)
            )
            .background(
                palette.accentSoft.copy(
                    alpha = 0.18f
                )
            )
            .padding(
                horizontal = 14.dp,
                vertical = 13.dp,
            )
            .testTag(
                "customerProblemCheck"
            ),
        verticalArrangement =
            Arrangement.spacedBy(10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement =
                Arrangement.SpaceBetween,
            verticalAlignment =
                Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement =
                    Arrangement.spacedBy(3.dp),
            ) {
                Row(
                    horizontalArrangement =
                        Arrangement.spacedBy(8.dp),
                    verticalAlignment =
                        Alignment.CenterVertically,
                ) {
                    Text(
                        text = title,
                        style =
                            MaterialTheme.typography
                                .titleLarge,
                        color = palette.accent,
                        fontWeight =
                            FontWeight.Black,
                    )

                    if (
                        !hasActiveInquiry &&
                        !previewMode
                    ) {
                        Box(
                            modifier = Modifier
                                .clip(
                                    RoundedCornerShape(
                                        999.dp
                                    )
                                )
                                .background(
                                    Color.White.copy(
                                        alpha = 0.82f
                                    )
                                )
                                .padding(
                                    horizontal = 9.dp,
                                    vertical = 4.dp,
                                ),
                        ) {
                            Text(
                                text =
                                    "3단계로 빠르게",
                                style =
                                    MaterialTheme
                                        .typography
                                        .labelMedium,
                                color =
                                    palette.accent,
                                fontWeight =
                                    FontWeight.Bold,
                            )
                        }
                    }
                }

                Text(
                    text = subtitle,
                    style =
                        MaterialTheme.typography
                            .bodyMedium,
                    color = palette.textMuted,
                )
            }

            if (
                hasActiveInquiry ||
                intakeAvailable
            ) {
                Box(
                    modifier = Modifier
                        .size(50.dp)
                        .clip(CircleShape)
                        .background(
                            palette.accent
                        )
                        .clickable {
                            if (hasActiveInquiry) {
                                onOpenInquiry(
                                    requireNotNull(
                                        activeInquiryId
                                    )
                                )
                            } else {
                                onStartIntake(
                                    home.subscriptionId
                                )
                            }
                        }
                        .testTag(
                            "problemCheckArrow"
                        ),
                    contentAlignment =
                        Alignment.Center,
                ) {
                    Text(
                        text = "→",
                        style =
                            MaterialTheme.typography
                                .headlineSmall,
                        color = Color.White,
                        fontWeight =
                            FontWeight.Black,
                    )
                }
            }
        }

        if (
            !previewMode &&
            !hasActiveInquiry &&
            intakeAvailable
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(7.dp),
            ) {
                FinalProblemChip(
                    text = "물이 약해요",
                    onClick = {
                        onStartIntake(
                            home.subscriptionId
                        )
                    },
                    modifier =
                        Modifier.weight(1f),
                )

                FinalProblemChip(
                    text = "물맛이 이상해요",
                    onClick = {
                        onStartIntake(
                            home.subscriptionId
                        )
                    },
                    modifier =
                        Modifier.weight(1f),
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement =
                    Arrangement.spacedBy(7.dp),
            ) {
                FinalProblemChip(
                    text = "소리가 나요",
                    onClick = {
                        onStartIntake(
                            home.subscriptionId
                        )
                    },
                    modifier =
                        Modifier.weight(1f),
                )

                FinalProblemChip(
                    text = "누수가 보여요",
                    onClick = {
                        onStartIntake(
                            home.subscriptionId
                        )
                    },
                    modifier =
                        Modifier.weight(1f),
                )
            }
        } else if (hasActiveInquiry) {
            ReferenceGlassButton(
                text = actionText,
                palette = palette,
                onClick = {
                    onOpenInquiry(
                        requireNotNull(
                            activeInquiryId
                        )
                    )
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(
                        "problemCheckActiveAction"
                    ),
            )
        }
    }
}

@Composable
private fun FinalProblemChip(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette

    Box(
        modifier = modifier
            .clip(
                RoundedCornerShape(999.dp)
            )
            .background(
                Color.White.copy(
                    alpha = 0.82f
                )
            )
            .clickable(onClick = onClick)
            .padding(
                horizontal = 10.dp,
                vertical = 10.dp,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            modifier =
                Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
            style =
                MaterialTheme.typography
                    .labelLarge,
            color = palette.textStrong,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
        )
    }
}

@Composable
fun FinalCustomerCareOverviewCard(
    home: CustomerHomeData,
    activeInquiryStatusCode: String?,
    previewMode: Boolean = false,
    onOpenCare: () -> Unit,
) {
    val palette = CustomerReferencePalette

    val requestText =
        when (
            activeInquiryStatusCode
                ?.trim()
                ?.uppercase()
                .orEmpty()
        ) {
            "" ->
                "접수된 요청이 없어요"
            "DRAFT",
            "QUESTIONNAIRE_IN_PROGRESS" ->
                "문진 작성 중이에요"
            "AI_GUIDANCE" ->
                "해결 방법이 준비됐어요"
            "CONSULTATION_REQUIRED",
            "CONSULTATION_IN_PROGRESS",
            "VISIT_REVIEW_PENDING",
            "VISIT_SCHEDULING",
            "VISIT_SCHEDULED",
            "COMPLETION_PENDING",
            "REVISIT_REQUIRED",
            "REOPENED" ->
                "요청을 처리하고 있어요"
            else ->
                "진행 상태를 확인해보세요"
        }

    CustomerCleanCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(
                "customerCareOverview"
            ),
        contentPadding = PaddingValues(
            horizontal = 15.dp,
            vertical = 14.dp,
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement =
                Arrangement.SpaceBetween,
            verticalAlignment =
                Alignment.CenterVertically,
        ) {
            Text(
                text = "케어 관리 현황",
                style =
                    MaterialTheme.typography
                        .titleMedium,
                color = palette.textStrong,
                fontWeight = FontWeight.Bold,
            )

            TextButton(
                onClick = onOpenCare,
            ) {
                Text(
                    text = "관리 보기 ›",
                    color = palette.accent,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement =
                Arrangement.spacedBy(8.dp),
        ) {
            FinalCareStatusTile(
                title = "다음 케어",
                value =
                    if (previewMode) {
                        "미리보기"
                    } else {
                        home.nextCareOn
                            ?: "확인 중"
                    },
                modifier = Modifier.weight(1f),
            )

            FinalCareStatusTile(
                title = "신청 현황",
                value =
                    if (previewMode) {
                        "구독 없음"
                    } else {
                        requestText
                    },
                modifier = Modifier.weight(1f),
            )

            FinalCareStatusTile(
                title = "최근 케어",
                value =
                    if (previewMode) {
                        "미리보기"
                    } else {
                        home.lastCareOn
                            ?: "확인 중"
                    },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun FinalCareStatusTile(
    title: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette

    Column(
        modifier = modifier
            .clip(
                RoundedCornerShape(14.dp)
            )
            .background(
                palette.accentSoft.copy(
                    alpha = 0.14f
                )
            )
            .padding(
                horizontal = 8.dp,
                vertical = 10.dp,
            ),
        horizontalAlignment =
            Alignment.CenterHorizontally,
        verticalArrangement =
            Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text = title,
            style =
                MaterialTheme.typography
                    .labelMedium,
            color = palette.textMuted,
            textAlign = TextAlign.Center,
        )

        Text(
            text = value,
            style =
                MaterialTheme.typography
                    .bodySmall,
            color = palette.textStrong,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            maxLines = 2,
        )
    }
}

@Composable
fun FinalCustomerCareHelpBanner(
    onOpenCare: () -> Unit,
) {
    val palette = CustomerReferencePalette

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(
                RoundedCornerShape(18.dp)
            )
            .background(
                palette.accentSoft.copy(
                    alpha = 0.20f
                )
            )
            .clickable(
                onClick = onOpenCare
            )
            .padding(
                horizontal = 16.dp,
                vertical = 14.dp,
            )
            .testTag(
                "customerCareHelp"
            ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement =
                Arrangement.SpaceBetween,
            verticalAlignment =
                Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement =
                    Arrangement.spacedBy(3.dp),
            ) {
                Text(
                    text =
                        "필터 관리가 궁금하신가요?",
                    style =
                        MaterialTheme.typography
                            .titleSmall,
                    color = palette.accent,
                    fontWeight = FontWeight.Bold,
                )

                Text(
                    text =
                        "관리 화면에서 우리 집 정수기 정보를 자세히 확인하세요.",
                    style =
                        MaterialTheme.typography
                            .bodySmall,
                    color = palette.textMuted,
                )
            }

            Text(
                text = "›",
                style =
                    MaterialTheme.typography
                        .headlineSmall,
                color = palette.accent,
                fontWeight = FontWeight.Black,
            )
        }
    }
}

@Composable
private fun CustomerFilterSummary(
    percent: Int,
    progress: Float,
    message: String,
    accentColor: Color,
) {
    val palette = CustomerReferencePalette
    val safeProgress = progress.coerceIn(0f, 1f)

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "필터 상태",
                style = MaterialTheme.typography.labelLarge,
                color = palette.textMuted,
                fontWeight = FontWeight.Medium,
            )
            Text(
                text = "${percent}% 남음",
                style = MaterialTheme.typography.titleSmall,
                color = palette.textStrong,
                fontWeight = FontWeight.Bold,
            )
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(7.dp)
                .clip(RoundedCornerShape(999.dp))
                .background(palette.accentSoft.copy(alpha = 0.30f)),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(safeProgress)
                    .height(7.dp)
                    .clip(RoundedCornerShape(999.dp))
                    .background(accentColor.copy(alpha = 0.86f)),
            )
        }

        Text(
            text = message,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Start,
            style = MaterialTheme.typography.bodySmall,
            color = palette.textMuted,
        )
    }
}

@Composable
fun CustomerServiceConnectionBanner(
    backendAvailable: Boolean?,
    offlinePreview: Boolean,
    hasActiveInquiry: Boolean,
    intakeAvailable: Boolean,
) {
    val palette = CustomerReferencePalette
    val statusText = when {
        offlinePreview -> "미리보기"
        backendAvailable == true -> "연결됨"
        backendAvailable == false -> "연결 필요"
        else -> "확인 중"
    }
    val detail = when {
        offlinePreview ->
            "화면 미리보기 중이에요. 실제 문의는 전송되지 않아요."
        backendAvailable == true && hasActiveInquiry ->
            "정수기와 진행 중인 문의가 안전하게 연결되어 있어요."
        backendAvailable == true && intakeAvailable ->
            "정수기 정보가 연결되어 바로 도움을 받을 수 있어요."
        backendAvailable == true ->
            "정수기 정보가 안전하게 연결되어 있어요."
        backendAvailable == false ->
            "연결을 확인하면 정수기 정보와 문의 기능을 이용할 수 있어요."
        else ->
            "서비스 연결 상태를 확인하고 있어요."
    }

    CustomerCleanCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("customerServiceConnection"),
        contentPadding = PaddingValues(
            horizontal = 13.dp,
            vertical = 10.dp,
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(palette.accentSoft.copy(alpha = 0.24f)),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(R.drawable.ref_notice),
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
            }

            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = "서비스 연결",
                    style = MaterialTheme.typography.labelLarge,
                    color = palette.textStrong,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = detail,
                    style = MaterialTheme.typography.bodyMedium,
                    color = palette.textMuted,
                )
            }

            HomeStatusPill(
                text = statusText,
                accent = backendAvailable == true && !offlinePreview,
            )
        }
    }
}

@Composable
fun CustomerVisualInquiryAction(
    home: CustomerHomeData,
    activeInquiryId: String?,
    activeInquiryStatusCode: String?,
    intakeAvailable: Boolean,
    intakeUnavailableReason: String?,
    previewMode: Boolean = false,
    onStartIntake: (String) -> Unit,
    onOpenInquiry: (String) -> Unit,
) {
    val palette = CustomerReferencePalette
    val hasActiveInquiry =
        !activeInquiryId.isNullOrBlank()
    val normalizedStatus =
        activeInquiryStatusCode
            ?.trim()
            ?.uppercase()
            .orEmpty()

    val needsQuestionnaire =
        normalizedStatus == "DRAFT" ||
            normalizedStatus ==
                "QUESTIONNAIRE_IN_PROGRESS"

    val isAiGuidance =
        normalizedStatus == "AI_GUIDANCE"

    val isConsultationOrVisit =
        normalizedStatus in setOf(
            "CONSULTATION_REQUIRED",
            "CONSULTATION_IN_PROGRESS",
            "VISIT_REVIEW_PENDING",
            "VISIT_SCHEDULING",
            "VISIT_SCHEDULED",
            "COMPLETION_PENDING",
            "REVISIT_REQUIRED",
            "REOPENED",
        )

    val isResolved =
        normalizedStatus == "RESOLVED"

    val statusLabel = when {
        previewMode ->
            "미리보기"

        needsQuestionnaire ->
            "확인 필요"

        isAiGuidance ->
            "맞춤 안내 준비됨"

        isConsultationOrVisit ->
            "처리 진행 중"

        isResolved ->
            "처리 완료"

        hasActiveInquiry ->
            "진행 중"

        intakeAvailable ->
            "바로 확인"

        else ->
            "도움 준비 중"
    }

    val headline = when {
        previewMode ->
            "실제 구독 제품을 선택해주세요"

        needsQuestionnaire ->
            "증상 확인을 조금만 더 해주세요"

        isAiGuidance ->
            "맞춤 해결 방법이 준비됐어요"

        isConsultationOrVisit ->
            "문의 처리 상태를 확인해보세요"

        isResolved ->
            "문의 처리가 완료됐어요"

        hasActiveInquiry ->
            "진행 중인 문의를 이어서 확인해주세요"

        intakeAvailable ->
            "정수기 사용이 불편하신가요?"

        else ->
            "도움 기능을 준비하고 있어요"
    }

    val description = when {
        previewMode ->
            "구독 중인 정수기를 선택하면 관리 정보와 증상 확인 기능을 사용할 수 있어요."

        needsQuestionnaire ->
            "몇 가지 간단한 질문에 답하면 상황에 맞는 안내를 받을 수 있어요."

        isAiGuidance ->
            "입력한 증상 정보를 바탕으로 준비된 해결 방법을 확인해보세요."

        isConsultationOrVisit ->
            inquiryStatusMessage(
                activeInquiryStatusCode.orEmpty()
            )

        isResolved ->
            "완료된 문의 내용과 처리 결과를 다시 확인할 수 있어요."

        hasActiveInquiry ->
            inquiryStatusMessage(
                activeInquiryStatusCode.orEmpty()
            )

        intakeAvailable -> {
            val nextCare = careDday(home.nextCareOn)
            if (nextCare == "확인 중") {
                "몇 가지 간단한 질문으로 증상을 확인하고 필요한 도움을 받을 수 있어요."
            } else {
                "다음 관리 $nextCare · 불편한 점이 생기면 바로 증상 확인을 시작할 수 있어요."
            }
        }

        else ->
            intakeUnavailableReason
                ?.takeIf { it.isNotBlank() }
                ?: "선택한 제품의 문의 가능 상태를 확인하고 있어요."
    }

    val actionText = when {
        needsQuestionnaire ->
            "문제 확인 이어서"

        isAiGuidance ->
            "맞춤 안내 확인하기"

        isConsultationOrVisit ->
            "진행 상황 보기"

        isResolved ->
            "처리 결과 보기"

        hasActiveInquiry ->
            "진행 상황 보기"

        else ->
            "문제 확인 시작"
    }

    CustomerCleanCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("customerTodayAction"),
        contentPadding = PaddingValues(
            horizontal = 16.dp,
            vertical = 14.dp,
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement =
                Arrangement.SpaceBetween,
            verticalAlignment =
                Alignment.CenterVertically,
        ) {
            Text(
                text = "지금 확인해주세요",
                style = MaterialTheme.typography.titleMedium,
                color = palette.textStrong,
                fontWeight = FontWeight.Bold,
            )

            HomeStatusPill(
                text = statusLabel,
                accent =
                    needsQuestionnaire ||
                        isAiGuidance,
            )
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 2.dp),
            horizontalArrangement =
                Arrangement.spacedBy(12.dp),
            verticalAlignment =
                Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .background(
                        palette.accentSoft.copy(
                            alpha = 0.28f
                        )
                    ),
                contentAlignment = Alignment.Center,
            ) {
                Image(
                    painter = painterResource(
                        when {
                            needsQuestionnaire ->
                                R.drawable.ref_intake
                            isAiGuidance ->
                                R.drawable.ref_care
                            isConsultationOrVisit ->
                                R.drawable.ref_notice
                            else ->
                                R.drawable.ref_intake
                        }
                    ),
                    contentDescription = null,
                    modifier = Modifier.size(23.dp),
                )
            }

            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement =
                    Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = headline,
                    style = MaterialTheme.typography.titleMedium,
                    color = palette.textStrong,
                    fontWeight = FontWeight.Bold,
                )

                Text(
                    text = description,
                    style = MaterialTheme.typography.bodySmall,
                    color = palette.textMuted,
                )
            }
        }

        if (hasActiveInquiry || intakeAvailable) {
            CustomerPrimaryButton(
                text = actionText,
                enabled = true,
                onClick = {
                    if (hasActiveInquiry) {
                        onOpenInquiry(
                            requireNotNull(activeInquiryId)
                        )
                    } else {
                        onStartIntake(
                            home.subscriptionId
                        )
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(
                        if (hasActiveInquiry) {
                            "heroOpenInquiry"
                        } else {
                            "heroStartIntake"
                        }
                    ),
            )

            if (hasActiveInquiry) {
                Text(
                    text = "마지막으로 진행하던 단계에서 바로 이어집니다.",
                    modifier = Modifier.fillMaxWidth(),
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.labelMedium,
                    color = palette.textMuted,
                )
            }
        } else if (!previewMode) {
            Text(
                text = description,
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.bodySmall,
                color = palette.textMuted,
            )
        }
    }
}

@Composable
fun CustomerQuickStatusRow(
    home: CustomerHomeData,
    previewMode: Boolean = false,
    onOpenCare: () -> Unit,
) {
    val nextCare =
        if (previewMode) "미리보기"
        else careDday(home.nextCareOn)
    val managementValue =
        if (previewMode) {
            "구독 없음"
        } else {
            when (home.product.managementTypeCode) {
                "VISIT_CARE" -> "방문"
                "SELF_MANAGED" -> "자가"
                else -> home.product.managementTypeLabel
            }
        }
    val nextCareLabel = if (home.product.managementTypeCode == "VISIT_CARE") {
        "다음 방문"
    } else {
        "다음 관리"
    }

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("customerProductInfo"),
    ) {
        if (maxWidth < 350.dp) {
            Column(
                verticalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(9.dp),
                ) {
                    QuickStatusTile(
                        iconRes = R.drawable.ref_event,
                        value = nextCare,
                        label = nextCareLabel,
                        modifier = Modifier.weight(1f),
                    )
                    QuickStatusTile(
                        iconRes = R.drawable.ref_manage,
                        value = managementValue,
                        label = "관리 방식",
                        modifier = Modifier.weight(1f),
                    )
                }
                QuickStatusTile(
                    iconRes = R.drawable.ref_care,
                    value = "보기",
                    label = "관리 기록",
                    onClick =
                        if (previewMode) null
                        else onOpenCare,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                QuickStatusTile(
                    iconRes = R.drawable.ref_event,
                    value = nextCare,
                    label = nextCareLabel,
                    modifier = Modifier.weight(1f),
                )
                QuickStatusTile(
                    iconRes = R.drawable.ref_manage,
                    value = managementValue,
                    label = "관리 방식",
                    modifier = Modifier.weight(1f),
                )
                QuickStatusTile(
                    iconRes = R.drawable.ref_care,
                    value = "보기",
                    label = "관리 기록",
                    onClick =
                        if (previewMode) null
                        else onOpenCare,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun QuickStatusTile(
    iconRes: Int,
    value: String,
    label: String,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
) {
    val palette = CustomerReferencePalette
    val clickModifier = if (onClick == null) {
        modifier
    } else {
        modifier.clickable(onClick = onClick)
    }

    CustomerCleanCard(
        modifier = clickModifier,
        contentPadding = PaddingValues(
            horizontal = 8.dp,
            vertical = 10.dp,
        ),
    ) {
        Box(
            modifier = Modifier
                .size(34.dp)
                .clip(CircleShape)
                .background(palette.accentSoft.copy(alpha = 0.22f))
                .align(Alignment.CenterHorizontally),
            contentAlignment = Alignment.Center,
        ) {
            Image(
                painter = painterResource(iconRes),
                contentDescription = label,
                modifier = Modifier.size(20.dp),
            )
        }

        Text(
            text = value,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 2.dp),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.titleMedium,
            color = palette.textStrong,
            fontWeight = FontWeight.Bold,
            maxLines = 1,
        )

        Text(
            text = label,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.labelMedium,
            color = palette.textMuted,
            maxLines = 1,
        )
    }
}

@Composable
private fun FilterRemainingRing(
    progress: Float,
    accentColor: androidx.compose.ui.graphics.Color =
        MaterialTheme.colorScheme.primary,
    trackColor: androidx.compose.ui.graphics.Color =
        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.38f),
    modifier: Modifier = Modifier,
) {
    val safeProgress = progress.coerceIn(0f, 1f)

    Canvas(modifier = modifier) {
        val stroke = 10.dp.toPx()
        val inset = stroke / 2f
        val arcSize = Size(
            width = size.width - stroke,
            height = size.height - stroke,
        )
        val startAngle = 135f
        val totalSweep = 270f
        val progressSweep = totalSweep * safeProgress

        drawArc(
            color = trackColor,
            startAngle = startAngle,
            sweepAngle = totalSweep,
            useCenter = false,
            topLeft = Offset(inset, inset),
            size = arcSize,
            style = Stroke(
                width = stroke,
                cap = StrokeCap.Round,
            ),
        )

        if (safeProgress > 0f) {
            drawArc(
                color = accentColor.copy(alpha = 0.92f),
                startAngle = startAngle,
                sweepAngle = progressSweep,
                useCenter = false,
                topLeft = Offset(inset, inset),
                size = arcSize,
                style = Stroke(
                    width = stroke,
                    cap = StrokeCap.Round,
                ),
            )

            val endAngle =
                Math.toRadians(
                    (startAngle + progressSweep).toDouble()
                )
            val radius =
                (size.minDimension - stroke) / 2f
            val marker = Offset(
                x = center.x +
                    cos(endAngle).toFloat() * radius,
                y = center.y +
                    sin(endAngle).toFloat() * radius,
            )

            drawCircle(
                color = Color.White.copy(alpha = 0.98f),
                radius = 6.dp.toPx(),
                center = marker,
            )
            drawCircle(
                color = accentColor,
                radius = 3.3.dp.toPx(),
                center = marker,
            )
        }
    }
}


@Composable
private fun HomeStatusPill(
    text: String,
    accent: Boolean,
) {
    val palette = CustomerReferencePalette

    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(
                if (accent) {
                    palette.accent.copy(alpha = 0.12f)
                } else {
                    palette.accentSoft.copy(alpha = 0.22f)
                }
            )
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelMedium,
            color =
                if (accent) palette.accent
                else palette.textMuted,
            fontWeight = FontWeight.Bold,
        )
    }
}

private data class RemainingFilterEstimate(
    val percent: Int,
    val progress: Float,
    val message: String,
)

private fun calculateRemainingFilterEstimate(
    home: CustomerHomeData,
    today: LocalDate = LocalDate.now(),
): RemainingFilterEstimate? {
    val lastCare = parseDate(home.lastCareOn)
    val started = parseDate(home.startedOn)
    val nextCare = parseDate(home.nextCareOn)
    val baseDate = lastCare ?: started ?: return null
    val endDate = nextCare ?: return null

    val totalDays = ChronoUnit.DAYS.between(baseDate, endDate)
    if (totalDays <= 0L) return null

    val elapsedDays = ChronoUnit.DAYS.between(baseDate, today)
        .coerceAtLeast(0L)
    val usedProgress = (
        elapsedDays.toDouble() / totalDays.toDouble()
        ).coerceIn(0.0, 1.0)
    val remainingProgress = (1.0 - usedProgress)
        .coerceIn(0.0, 1.0)
        .toFloat()
    val remainingDays = ChronoUnit.DAYS.between(today, endDate)
    val remainingPercent = (remainingProgress * 100f)
        .roundToInt()
        .coerceIn(0, 100)

    return RemainingFilterEstimate(
        percent = remainingPercent,
        progress = remainingProgress,
        message = when {
            remainingDays > 0L -> "다음 관리까지 약 ${remainingDays}일 남았어요."
            remainingDays == 0L -> "오늘이 다음 관리 예정일이에요."
            else -> "다음 관리 예정일이 지났어요."
        },
    )
}

private fun careDday(
    value: String?,
    today: LocalDate = LocalDate.now(),
): String {
    val date = parseDate(value) ?: return "확인 중"
    val days = ChronoUnit.DAYS.between(today, date)
    return when {
        days > 0L -> "D-$days"
        days == 0L -> "D-DAY"
        else -> "D+${-days}"
    }
}

private fun parseDate(value: String?): LocalDate? {
    val normalized = value
        ?.trim()
        ?.takeIf { it.isNotBlank() && !it.equals("미정", ignoreCase = true) }
        ?.take(10)
        ?: return null
    return runCatching { LocalDate.parse(normalized) }.getOrNull()
}

private fun inquiryStatusMessage(statusCode: String): String = when (
    statusCode.trim().uppercase()
) {
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
