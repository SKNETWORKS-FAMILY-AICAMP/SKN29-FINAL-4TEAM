package com.skn29.watercare.customer.feature.customer.home

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.skn29.watercare.core.config.CustomerCareMode
import com.skn29.watercare.core.model.CustomerHomeData
import com.skn29.watercare.core.model.isP0SupportedActiveSubscription
import com.skn29.watercare.core.ui.components.CustomerReferencePalette
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.ReferenceGlassButton
import com.skn29.watercare.core.ui.components.ReferenceSectionHeader
import kotlin.math.absoluteValue

@Composable
fun SubscriptionSelectionScreen(
    state: CustomerHomeUiState,
    initialModelCode: String? = null,
    onConfirm: (CustomerModelSelection) -> Unit,
    onRetry: () -> Unit,
    onLogout: () -> Unit,
) {
    val palette = CustomerReferencePalette
    val subscriptions = state.subscriptions
    val models = CustomerModelCatalog

    val selectedSubscriptionModelCode = subscriptions
        .firstOrNull {
            it.subscriptionId == state.selectedSubscriptionId
        }
        ?.product
        ?.modelCode

    val initialPage = remember(
        initialModelCode,
        selectedSubscriptionModelCode,
    ) {
        val targetCode = initialModelCode
            ?.takeIf(String::isNotBlank)
            ?: selectedSubscriptionModelCode

        models.indexOfFirst {
            it.modelCode.equals(
                targetCode,
                ignoreCase = true,
            )
        }.takeIf { it >= 0 } ?: 0
    }
    val pagerState = rememberPagerState(
        initialPage = initialPage,
        pageCount = { models.size },
    )

    CustomerCleanScaffold(
        displayName = state.user?.displayName,
        showBottomBar = false,
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = "내 정수기",
                style = MaterialTheme.typography.headlineSmall,
                color = palette.textStrong,
                fontWeight = FontWeight.Black,
            )
            Text(
                text = "세 가지 모델을 넘겨보며 가장 맞는 제품을 선택해보세요.",
                style = MaterialTheme.typography.bodyMedium,
                color = palette.textMuted,
            )
        }

        state.error?.let { message ->
            ErrorCard(
                message = message,
                onRetry = onRetry,
            )
        }

        if (subscriptions.isEmpty() && state.error == null) {
            Text(
                text = "연결된 구독이 없어 모델 미리보기만 사용할 수 있어요.",
                style = MaterialTheme.typography.bodySmall,
                color = palette.textMuted,
            )
        }

        HorizontalPager(
            state = pagerState,
            modifier = Modifier
                .fillMaxWidth()
                .height(336.dp)
                .testTag("subscriptionPager"),
            contentPadding = PaddingValues(horizontal = 18.dp),
            pageSpacing = 10.dp,
        ) { page ->
            val model = models[page]
            val subscription = subscriptions.firstOrNull {
                it.product.modelCode.equals(
                    model.modelCode,
                    ignoreCase = true,
                )
            }
            val signedPageOffset =
                (
                    (pagerState.currentPage - page) +
                        pagerState
                            .currentPageOffsetFraction
                    ).coerceIn(-1f, 1f)
            val pageOffset =
                signedPageOffset
                    .absoluteValue
                    .coerceIn(0f, 1f)
            val focus = 1f - pageOffset

            val settleScale by
                animateFloatAsState(
                    targetValue =
                        if (pageOffset < 0.06f) {
                            1.10f
                        } else {
                            0.96f
                        },
                    animationSpec = spring(
                        dampingRatio =
                            Spring.DampingRatioHighBouncy,
                        stiffness =
                            Spring.StiffnessMediumLow,
                    ),
                    label = "modelSettleBounce",
                )
            SubscriptionProductSlide(
                model = model,
                subscription = subscription,
                activeInquiry =
                    subscription != null &&
                        state.activeInquiry?.subscriptionId ==
                        subscription.subscriptionId,
                modifier = Modifier.graphicsLayer {
                    scaleX =
                        (0.84f +
                            (0.16f * focus)) *
                            settleScale
                    scaleY =
                        (0.84f +
                            (0.16f * focus)) *
                            settleScale
                    alpha = 0.48f + (0.52f * focus)
                    translationY = 24f * pageOffset
                    rotationY =
                        signedPageOffset * 16f
                    cameraDistance =
                        18f * density
                },
            )
        }

        SubscriptionPageIndicator(
            pageCount = models.size,
            selectedPage = pagerState.currentPage,
            modifier = Modifier.fillMaxWidth(),
        )

        Text(
            text =
                "${pagerState.currentPage + 1} / ${models.size}",
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.labelMedium,
            color = palette.textMuted,
        )

        val selectedModel = models.getOrNull(
            pagerState.currentPage
        )
        val selectedSubscription = selectedModel?.let { model ->
            subscriptions.firstOrNull {
                it.product.modelCode.equals(
                    model.modelCode,
                    ignoreCase = true,
                )
            }
        }

        CustomerPrimaryButton(
            text = when {
                state.selectingSubscription ->
                    "제품 연결 중..."
                selectedSubscription == null ->
                    "홈에서 이 모델 미리보기"
                else ->
                    "이 제품으로 시작"
            },
            enabled =
                selectedModel != null &&
                    !state.selectingSubscription,
            onClick = {
                selectedModel?.let { model ->
                    onConfirm(
                        CustomerModelSelection(
                            modelCode = model.modelCode,
                            subscriptionId =
                                selectedSubscription?.subscriptionId,
                        )
                    )
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .testTag("confirmSubscriptionSelection"),
        )

        if (selectedModel != null && selectedSubscription == null) {
            Text(
                text = "미연결 모델은 홈 디자인만 미리 볼 수 있고 문의 기능은 실행되지 않아요.",
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.bodySmall,
                color = palette.textMuted,
            )
        }

        CustomerTextAction(
            text = "로그아웃",
            enabled = !state.loggingOut && !state.selectingSubscription,
            onClick = onLogout,
            modifier = Modifier.align(Alignment.CenterHorizontally),
        )
    }
}

@Composable
private fun SubscriptionProductSlide(
    model: CustomerModelVisualSpec,
    subscription: CustomerHomeData?,
    activeInquiry: Boolean,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette
    val supported =
        subscription?.isP0SupportedActiveSubscription() == true
    val connected = subscription != null

    CustomerCleanCard(
        modifier = modifier
            .fillMaxWidth()
            .testTag(
                "subscription_${subscription?.subscriptionId ?: model.modelCode}"
            ),
        contentPadding = PaddingValues(
            horizontal = 16.dp,
            vertical = 14.dp,
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            StatusChip(
                text = when (
                    subscription
                        ?.statusCode
                        ?.trim()
                        ?.uppercase()
                ) {
                    "ACTIVE" -> "사용 중"
                    "PAUSED" -> "이용 일시정지"
                    "ENDED", "CANCELLED" -> "이용 종료"
                    null -> "미연결"
                    else -> "구독 상태 확인"
                },
                emphasized =
                    subscription?.statusCode == "ACTIVE",
            )
            when {
                activeInquiry -> {
                    StatusChip(
                        text = "문의 진행 중",
                        emphasized = true,
                    )
                }
                !connected -> {
                    StatusChip(
                        text = "미리보기",
                        emphasized = false,
                    )
                }
            }
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(142.dp),
            contentAlignment = Alignment.Center,
        ) {
            CustomerModelMascot(
                model = model,
                modifier = Modifier.size(128.dp),
            )
        }

        Text(
            text = subscription
                ?.product
                ?.modelName
                ?.takeIf(String::isNotBlank)
                ?: model.modelName,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.titleMedium,
            color = palette.textStrong,
            fontWeight = FontWeight.Bold,
        )
        Text(
            text = model.modelCode,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodySmall,
            color = palette.textMuted,
            fontWeight = FontWeight.SemiBold,
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            StatusChip(
                text = subscription
                    ?.product
                    ?.managementTypeLabel
                    ?.takeIf(String::isNotBlank)
                    ?: "미리보기",
                emphasized = false,
            )
            Spacer(modifier = Modifier.size(8.dp))
            StatusChip(
                text = when {
                    supported -> "문의 가능"
                    connected -> "문의 준비 중"
                    else -> "연결 후 문의"
                },
                emphasized = supported,
            )
        }

        Text(
            text = if (connected) {
                "다음 관리 ${formatCareDate(subscription?.nextCareOn)}"
            } else {
                "구독 연결 후 관리 일정이 표시돼요."
            },
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.bodySmall,
            color = palette.textMuted,
        )
    }
}

@Composable
private fun StatusChip(
    text: String,
    emphasized: Boolean,
) {
    val palette = CustomerReferencePalette
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(
                if (emphasized) {
                    palette.accent.copy(alpha = 0.12f)
                } else {
                    palette.accentSoft.copy(alpha = 0.22f)
                }
            )
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(
            text = text,
            color = if (emphasized) palette.accent else palette.textMuted,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun SubscriptionPageIndicator(
    pageCount: Int,
    selectedPage: Int,
    modifier: Modifier = Modifier,
) {
    val palette = CustomerReferencePalette
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        repeat(pageCount) { index ->
            val width by animateDpAsState(
                targetValue =
                    if (index == selectedPage) {
                        38.dp
                    } else {
                        8.dp
                    },
                animationSpec = spring(
                    dampingRatio =
                        Spring.DampingRatioHighBouncy,
                    stiffness =
                        Spring.StiffnessMediumLow,
                ),
                label = "subscriptionIndicatorWidth",
            )
            Box(
                modifier = Modifier
                    .padding(horizontal = 4.dp)
                    .size(width = width, height = 8.dp)
                    .clip(RoundedCornerShape(999.dp))
                    .background(
                        if (index == selectedPage) {
                            palette.accent
                        } else {
                            palette.accent.copy(alpha = 0.20f)
                        }
                    ),
            )
        }
    }
}

@Composable
fun SubscriptionSelector(
    state: CustomerHomeUiState,
    onSelect: (String) -> Unit,
) {
    if (
        state.customerCareMode != CustomerCareMode.REMOTE ||
        state.offlinePreview ||
        state.subscriptions.isEmpty()
    ) {
        return
    }

    val palette = CustomerReferencePalette
    ReferenceSectionHeader(
        title = "내 정수기",
        trailing = if (state.subscriptions.size > 1) "제품 변경" else "사용 중",
        palette = palette,
    )
    CustomerCleanCard {
        state.subscriptions.forEach { subscription ->
            val selected =
                state.selectedSubscriptionId == subscription.subscriptionId
            ReferenceGlassButton(
                text = if (selected) {
                    "${subscription.product.modelName} · 선택됨"
                } else {
                    subscription.product.modelName
                },
                palette = palette,
                accent = selected,
                enabled = !selected && !state.selectingSubscription,
                onClick = { onSelect(subscription.subscriptionId) },
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("subscriptionCompact_${subscription.subscriptionId}"),
            )
        }
    }
}

private fun formatCareDate(value: String?): String {
    val normalized = value?.trim().orEmpty()
    if (normalized.isBlank() || normalized.equals("미정", ignoreCase = true)) {
        return "미정"
    }
    return normalized.take(10)
}
