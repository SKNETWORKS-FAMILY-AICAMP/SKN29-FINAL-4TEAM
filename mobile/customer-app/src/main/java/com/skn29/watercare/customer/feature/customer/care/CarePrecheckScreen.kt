@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.customer.feature.customer.care

import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.Lifecycle
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.ui.components.LiquidGlassButton
import com.skn29.watercare.core.ui.components.LiquidGlassPill
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.CustomerErrorState
import com.skn29.watercare.customer.feature.shared.CustomerInitialLoadingState
import com.skn29.watercare.customer.feature.shared.CustomerSubmittingState
import com.skn29.watercare.customer.feature.shared.SectionCard
import com.skn29.watercare.customer.feature.shared.WaterCareScreen

@Composable
fun CarePrecheckScreen(
    subscriptionId: String,
    onBack: () -> Unit,
    onAuthExpired: () -> Unit,
) {
    val viewModel: CarePrecheckViewModel =
        viewModel(
            factory =
                VmFactory { extras ->
                    CarePrecheckViewModel(
                        subscriptionId =
                            subscriptionId,
                        repository =
                            WaterCareCore
                                .carePrecheckRepository,
                        savedStateHandle =
                            extras
                                .createSavedStateHandle(),
                    )
                }
        )

    val state by
        viewModel.state
            .collectAsStateWithLifecycle()

    // 사전 점검을 작성하다 다른 화면에 다녀온 경우
    // Backend에 저장된 최신 session 상태를 다시 확인한다.
    // 단, 저장/제출 중에 재조회하면 경쟁 상태가 될 수 있어 그 동안은 제외한다.
    var hasResumedOnce by
        remember(subscriptionId) {
            mutableStateOf(false)
        }

    LifecycleEventEffect(
        Lifecycle.Event.ON_RESUME
    ) {
        if (
            hasResumedOnce &&
            !state.saving &&
            !state.submitting
        ) {
            viewModel.retry()
        } else {
            hasResumedOnce = true
        }
    }

    LaunchedEffect(state.authExpired) {
        if (state.authExpired) {
            viewModel.consumeAuthExpired()
            onAuthExpired()
        }
    }

    PullToRefreshBox(
        isRefreshing = state.refreshing,
        onRefresh = {
            if (
                !state.loading &&
                !state.saving &&
                !state.submitting
            ) {
                // 작성 중인 사전 점검 내용을 그대로 보여주고
                // 저장된 session의 최신 상태만 다시 확인한다.
                viewModel.refresh()
            }
        },
    ) {
        WaterCareScreen(
            title = "방문 전 사전 점검",
            onBack = onBack,
        ) {
            SectionCard("방문 전 미리 확인해요") {
                Text(
                    "현재 정수기 상태를 간단히 알려주시면 방문 관리 준비에 활용할 수 있어요."
                )
                Text(
                    "사전 점검만으로 문의가 자동 접수되지는 않아요.",
                    style =
                        MaterialTheme.typography
                            .bodySmall,
                    color =
                        MaterialTheme.colorScheme
                            .onSurfaceVariant,
                )
            }

            if (state.loading) {
                CustomerInitialLoadingState(
                    title =
                        "사전 점검을 불러오고 있어요",
                    message =
                        "저장된 점검 내용과 현재 상태를 확인하고 있어요.",
                )
                return@WaterCareScreen
            }

            state.notice?.let {
                SectionCard("저장 결과") {
                    Text(it)
                }
            }

            state.error?.let {
                CustomerErrorState(
                    title =
                        "사전 점검을 확인하지 못했어요",
                    message = it,
                    onRetry =
                        if (state.retryable) {
                            viewModel::retry
                        } else {
                            null
                        },
                )
            }

            val session = state.session
                ?: return@WaterCareScreen

            val completedCount =
                (if (state.waterFlow != null) 1 else 0) +
                    (if (state.leak != null) 1 else 0)

            SectionCard("진행 상태") {
                LiquidGlassPill(
                    when (session.statusCode) {
                        "UNANSWERED" -> "작성 전"
                        "IN_PROGRESS" -> "작성 중"
                        "SUBMITTED" -> "제출 완료"
                        else -> "상태 확인 중"
                    }
                )
                Text(
                    "점검 진행 $completedCount/2",
                    fontWeight = FontWeight.Bold,
                )
            }

            SectionCard(
                "1. 물이 평소처럼 나오나요?"
            ) {
                Column(
                    verticalArrangement =
                        Arrangement.spacedBy(8.dp),
                ) {
                    PrecheckChoice(
                        "평소와 비슷해요",
                        state.waterFlow == "NORMAL",
                        session.statusCode != "SUBMITTED",
                    ) {
                        viewModel
                            .selectWaterFlow("NORMAL")
                    }
                    PrecheckChoice(
                        "평소보다 약해요",
                        state.waterFlow == "LOW",
                        session.statusCode != "SUBMITTED",
                    ) {
                        viewModel
                            .selectWaterFlow("LOW")
                    }
                }
            }

            SectionCard(
                "2. 물이 새는 곳이 있나요?"
            ) {
                Column(
                    verticalArrangement =
                        Arrangement.spacedBy(8.dp),
                ) {
                    PrecheckChoice(
                        "없어요",
                        state.leak == false,
                        session.statusCode != "SUBMITTED",
                    ) {
                        viewModel.selectLeak(false)
                    }
                    PrecheckChoice(
                        "있어요",
                        state.leak == true,
                        session.statusCode != "SUBMITTED",
                    ) {
                        viewModel.selectLeak(true)
                    }
                }
            }

            if (
                state.saving ||
                state.submitting
            ) {
                // 저장과 최종 제출은 서로 다른 작업이므로
                // 현재 무슨 작업을 처리 중인지 문구를 달리 보여준다.
                CustomerSubmittingState(
                    message =
                        if (state.submitting) {
                            "사전 점검 결과를 제출하고 있어요."
                        } else {
                            "작성 중인 점검 내용을 임시 저장하고 있어요."
                        },
                )
            }

            if (session.statusCode != "SUBMITTED") {
                LiquidGlassButton(
                    text =
                        if (state.saving) {
                            "저장 중"
                        } else {
                            "임시 저장"
                        },
                    onClick = viewModel::save,
                    enabled =
                        !state.saving &&
                            !state.submitting,
                    accent = false,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag(
                            "saveCarePrecheck"
                        ),
                )

                LiquidGlassButton(
                    text =
                        if (state.submitting) {
                            "제출 중"
                        } else {
                            "사전 점검 제출"
                        },
                    onClick = viewModel::submit,
                    enabled =
                        !state.saving &&
                            !state.submitting &&
                            state.waterFlow != null &&
                            state.leak != null,
                    accent = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag(
                            "submitCarePrecheck"
                        ),
                )
            } else {
                LiquidGlassButton(
                    text = "케어 관리로 돌아가기",
                    onClick = onBack,
                    accent = true,
                    modifier =
                        Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

@Composable
private fun PrecheckChoice(
    text: String,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        enabled = enabled,
        label = {
            Text(
                text,
                modifier =
                    Modifier.fillMaxWidth(),
            )
        },
        modifier =
            Modifier.fillMaxWidth(),
    )
}
