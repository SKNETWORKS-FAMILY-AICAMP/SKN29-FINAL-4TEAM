@file:OptIn(
    androidx.compose.material3.ExperimentalMaterial3Api::class
)

package com.skn29.watercare.customer.feature.customer.care

import kotlinx.coroutines.delay
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.Spring
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.scaleIn
import androidx.compose.animation.fadeIn
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.CareHistoryItemDto
import com.skn29.watercare.core.model.CustomerSelfCareType
import com.skn29.watercare.core.ui.components.ErrorCard
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.customer.home.CustomerBottomTab
import com.skn29.watercare.customer.feature.customer.home.CustomerCleanBottomBar
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun CareHistoryScreen(
    onBack: () -> Unit,
    onAuthExpired: () -> Unit,
    onStartPrecheck: (String) -> Unit = {},
) {
    val viewModel: CareHistoryViewModel =
        viewModel(
            factory = VmFactory { _ ->
                CareHistoryViewModel(
                    subscriptionRepository =
                        WaterCareCore
                            .subscriptionRepository,
                    careHistoryRepository =
                        WaterCareCore
                            .careHistoryRepository,
                )
            }
        )

    val state by
        viewModel.state
            .collectAsStateWithLifecycle()

    LifecycleEventEffect(
        Lifecycle.Event.ON_RESUME
    ) {
        viewModel.load()
    }

    LaunchedEffect(state.authExpired) {
        if (state.authExpired) {
            viewModel.consumeAuthExpired()
            onAuthExpired()
        }
    }

    PullToRefreshBox(
        isRefreshing =
            state.loadingSubscriptions ||
                state.loadingHistory,
        onRefresh = viewModel::load,
    ) {
        CareHistoryContent(
            state = state,
            onBack = onBack,
            onRetry = viewModel::load,
            onSelectSubscription =
                viewModel::selectSubscription,
            onSelectCareType =
                viewModel::selectCareType,
            onPerformedOnChange =
                viewModel::updatePerformedOn,
            onCreate =
                viewModel::createCareRecord,
            onOpenDetail =
                viewModel::openDetail,
            onStartPrecheck =
                onStartPrecheck,
        )
    }
}

@Composable
fun CareHistoryContent(
    state: CareHistoryUiState,
    onBack: () -> Unit,
    onRetry: () -> Unit,
    onSelectSubscription:
        (String) -> Unit,
    onSelectCareType:
        (CustomerSelfCareType) -> Unit,
    onPerformedOnChange:
        (String) -> Unit,
    onCreate: () -> Unit,
    onOpenDetail: (String) -> Unit,
    onStartPrecheck: (String) -> Unit = {},
) {
    var visibleHistoryCount by remember(
        state.items.map {
            it.careRecordId
        }
    ) {
        mutableIntStateOf(0)
    }

    var showCreateConfirmation by remember {
        mutableStateOf(false)
    }

    LaunchedEffect(
        state.items.map {
            it.careRecordId
        }
    ) {
        visibleHistoryCount = 0

        state.items.indices.forEach { index ->
            delay(55)
            visibleHistoryCount = index + 1
        }
    }

    if (showCreateConfirmation) {
        AlertDialog(
            onDismissRequest = {
                showCreateConfirmation = false
            },
            title = {
                Text("케어 이력 등록")
            },
            text = {
                Text("선택한 관리 유형과 날짜로 케어 이력을 등록할까요?")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showCreateConfirmation = false
                        onCreate()
                    },
                ) {
                    Text("등록")
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        showCreateConfirmation = false
                    },
                ) {
                    Text("취소")
                }
            },
        )
    }

    WaterCareScreen(
        title = "케어 이력",
        onBack = onBack,
            bottomBar = {
            CustomerCleanBottomBar(
                selectedTab =
                    CustomerBottomTab.CARE,
                careEnabled = true,
                onOpenHome = onBack,
                onOpenCare = onRetry,
            )
        },
) {
        if (state.loadingSubscriptions) {
            // Visible loading UI intentionally hidden.
        }

        state.errorMessage?.let { message ->
            val retryable =
                state.errorKind ==
                    CareHistoryErrorKind.NETWORK ||
                    state.errorKind ==
                    CareHistoryErrorKind.SERVER

            ErrorCard(
                message = message,
                onRetry =
                    if (retryable) {
                        onRetry
                    } else {
                        null
                    },
            )
        }

        state.notice?.let { notice ->
            SectionCard("등록 결과") {
                Text(notice)
            }
        }

        if (
            !state.loadingSubscriptions &&
            state.subscriptions.isEmpty()
        ) {
            SectionCard("케어 이력") {
                Text(
                    "현재 고객 본인 명의의 관리 가능한 정수기가 없습니다."
                )
            }
            return@WaterCareScreen
        }

        if (state.subscriptions.isNotEmpty()) {
            SectionCard("관리할 정수기") {
                Text(
                    "현재 사용 중인 지원 정수기만 선택할 수 있어요.",
                    style =
                        MaterialTheme.typography
                            .bodySmall,
                    color =
                        MaterialTheme.colorScheme
                            .onSurfaceVariant,
                )

                Column(
                    verticalArrangement =
                        Arrangement.spacedBy(
                            8.dp
                        )
                ) {
                    state.subscriptions
                        .forEach { subscription ->
                            FilterChip(
                                selected =
                                    state
                                        .selectedSubscriptionId ==
                                        subscription
                                            .subscriptionId,
                                onClick = {
                                    onSelectSubscription(
                                        subscription
                                            .subscriptionId
                                    )
                                },
                                label = {
                                    Text(
                                        subscription
                                            .product
                                            .modelName
                                    )
                                },
                                modifier =
                                    Modifier
                                        .fillMaxWidth(),
                            )
                        }
                }
            }

            SectionCard("방문 전 사전 점검") {
                Text(
                    "방문 관리 전에 현재 상태를 간단히 확인하고 저장할 수 있어요.",
                    style =
                        MaterialTheme.typography
                            .bodySmall,
                    color =
                        MaterialTheme.colorScheme
                            .onSurfaceVariant,
                )

                LiquidGlassButton(
                    text = "사전 점검 시작하기",
                    onClick = {
                        state.selectedSubscriptionId
                            ?.let(onStartPrecheck)
                    },
                    enabled =
                        state.selectedSubscriptionId !=
                            null,
                    accent = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag(
                            "startCarePrecheck"
                        ),
                )
            }

            SectionCard("직접 관리 이력 등록") {
                Text(
                    "필터 교체와 청소만 직접 등록할 수 있어요.",
                    style =
                        MaterialTheme.typography
                            .bodySmall,
                    color =
                        MaterialTheme.colorScheme
                            .onSurfaceVariant,
                )

                Column(
                    verticalArrangement =
                        Arrangement.spacedBy(
                            8.dp
                        )
                ) {
                    CustomerSelfCareType.entries
                        .forEach { type ->
                            FilterChip(
                                selected =
                                    state
                                        .selectedCareType ==
                                        type,
                                onClick = {
                                    onSelectCareType(type)
                                },
                                label = {
                                    Text(
                                        careTypeLabel(
                                            type.code
                                        )
                                    )
                                },
                            )
                        }
                }

                OutlinedTextField(
                    value = state.performedOn,
                    onValueChange =
                        onPerformedOnChange,
                    label = {
                        Text(
                            "관리일 (YYYY-MM-DD)"
                        )
                    },
                    supportingText = {
                        Text(
                            "미래 날짜와 구독 시작 전 날짜는 등록할 수 없어요."
                        )
                    },
                    singleLine = true,
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .testTag(
                                "carePerformedOn"
                            ),
                )

                LiquidGlassButton(
                    text =
                        if (state.isCreating) {
                            "등록 중"
                        } else {
                            "케어 이력 등록하기"
                        },
                    onClick = {
                        showCreateConfirmation = true
                    },
                    enabled =
                        !state.isCreating &&
                            state
                                .selectedSubscriptionId !=
                            null,
                    accent = true,
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .testTag(
                                "careCreate"
                            ),
                )
            }

            SectionCard("완료된 케어 이력") {
                if (state.loadingHistory) {
                    // Visible loading UI intentionally hidden.
                } else if (
                    state.items.isEmpty()
                ) {
                    Text(
                        "아직 확인할 수 있는 완료 이력이 없습니다."
                    )
                } else {
                    Column(
                        verticalArrangement =
                            Arrangement.spacedBy(
                                12.dp
                            )
                    ) {
                        state.items.forEachIndexed {
                                index,
                                item,
                            ->
                            AnimatedVisibility(
                                visible =
                                    index <
                                        visibleHistoryCount,
                                enter =
                                    fadeIn() +
                                        slideInVertically(
                                            initialOffsetY = {
                                                (it * 0.92f).toInt()
                                            }
                                        ) +
                                        scaleIn(
                                            initialScale =
                                                0.76f
                                        ),
                            ) {
                                CareHistoryRow(
                                    item = item,
                                    onOpenDetail =
                                        onOpenDetail,
                                )
                            }
                        }
                    }
                }
            }

            state.detail?.let { item ->
                SectionCard(
                    title =
                        "선택한 케어 이력 상세"
                ) {
                    Text(
                        careTypeLabel(
                            item.careTypeCode
                        ),
                        fontWeight =
                            FontWeight.ExtraBold,
                    )
                    Text(
                        "관리일 · ${item.performedOn}"
                    )
                    Text(
                        "처리 결과 · ${
                            resultLabel(
                                item.resultCode
                            )
                        }"
                    )
                    Text(
                        "등록 경로 · ${
                            sourceLabel(
                                item.sourceCode
                            )
                        }"
                    )
                }
            }
        }
    }
}

@Composable
private fun CareHistoryRow(
    item: CareHistoryItemDto,
    onOpenDetail: (String) -> Unit,
) {
    Column(
        verticalArrangement =
            Arrangement.spacedBy(6.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(
            careTypeLabel(item.careTypeCode),
            fontWeight = FontWeight.Bold,
        )
        Text("관리일 · ${item.performedOn}")
        Text(
            "처리 결과 · ${
                resultLabel(item.resultCode)
            }"
        )
        LiquidGlassButton(
            text = "상세 보기",
            onClick = {
                onOpenDetail(
                    item.careRecordId
                )
            },
            compact = true,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .testTag(
                        "careDetail_${item.careRecordId}"
                    ),
        )
    }
}

private fun careTypeLabel(
    code: String,
): String = when (code) {
    "FILTER_REPLACEMENT" -> "필터 교체"
    "PERIODIC_CHECK" -> "정기 점검"
    "CLEANING" -> "청소"
    "VISIT_SERVICE" -> "방문 관리"
    else -> "기타 관리"
}

private fun resultLabel(
    code: String?,
): String = when (code) {
    "NORMAL" -> "정상 완료"
    "FILTER_REPLACED" -> "필터 교체 완료"
    "ISSUE_RESOLVED" -> "문제 해결 완료"
    else -> "완료"
}

private fun sourceLabel(
    code: String,
): String = when (code) {
    "CUSTOMER" -> "고객 직접 등록"
    "TECHNICIAN" -> "방문 기사"
    "CONSULTANT" -> "상담 처리"
    "SYSTEM" -> "서비스 처리"
    "IMPORT" -> "이전 관리 이력"
    else -> "서비스 처리"
}
