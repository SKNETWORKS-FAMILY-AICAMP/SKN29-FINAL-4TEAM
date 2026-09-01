@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.skn29.watercare.customer.feature.customer.guidance

import kotlinx.coroutines.delay
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.Lifecycle
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.CustomerInitialLoadingState
import com.skn29.watercare.customer.feature.shared.WaterCareScreen
import kotlinx.coroutines.flow.collect

@Composable
fun FollowUpQuestionsScreen(
    inquiryId: String,
    onBack: () -> Unit,
    onAuthExpired: () -> Unit = {},
    onCancelledStartOver:
        (String) -> Unit,
    onOpenGuidance:
        (CustomerInquirySnapshot) -> Unit,
) {
    val viewModel:
        FollowUpQuestionsViewModel =
        viewModel(
            factory =
                VmFactory { extras ->
                    FollowUpQuestionsViewModel(
                        inquiryId =
                            inquiryId,
                        repository =
                            WaterCareCore
                                .customerInquiryRepository,
                        inquiryRepository =
                            WaterCareCore
                                .inquiryRepository,
                        savedStateHandle =
                            extras.createSavedStateHandle(),
                    )
                }
        )

    val state by
        viewModel.state
            .collectAsStateWithLifecycle()

    val refreshing by
        viewModel.refreshing
            .collectAsStateWithLifecycle()


    // 최초 진입은 ViewModel의 load()가 담당하고,
    // 다른 화면에서 돌아온 경우에만 silent refresh를 수행한다.
    // silent refresh를 사용하면 작성 중인 답변을 지우지 않고
    // 서버의 최신 workflow 상태만 반영할 수 있다.
    var hasResumedOnce by
        remember(inquiryId) {
            mutableStateOf(false)
        }

    LifecycleEventEffect(
        Lifecycle.Event.ON_RESUME
    ) {
        if (hasResumedOnce) {
            viewModel.refreshSilently()
        } else {
            hasResumedOnce = true
        }
    }

    val awaitingBackendAdvance =
        state is FollowUpUiState.Empty &&
            state.snapshotOrNull()
                ?.statusCode
                ?.trim()
                ?.uppercase() ==
                "QUESTIONNAIRE_IN_PROGRESS"

    LaunchedEffect(
        inquiryId,
        awaitingBackendAdvance,
    ) {
        if (!awaitingBackendAdvance) {
            return@LaunchedEffect
        }

        repeat(12) {
            delay(2_500)

            val current =
                viewModel.state.value

            val stillWaiting =
                current is
                    FollowUpUiState.Empty &&
                    current.snapshot
                        .statusCode
                        .trim()
                        .uppercase() ==
                    "QUESTIONNAIRE_IN_PROGRESS"

            if (!stillWaiting) {
                return@LaunchedEffect
            }

            viewModel.refreshSilently()
        }
    }

    val cancelState by
        viewModel.cancelState
            .collectAsStateWithLifecycle()

    val authExpired by
        viewModel.authExpired
            .collectAsStateWithLifecycle()

    LaunchedEffect(authExpired) {
        if (authExpired) {
            viewModel.consumeAuthExpired()
            onAuthExpired()
        }
    }

    LaunchedEffect(cancelState) {
        if (
            cancelState is
                CancelInquiryUiState.Success
        ) {
            val subscriptionId =
                state.snapshotOrNull()
                    ?.subscriptionId
                    .orEmpty()
                    .trim()

            if (subscriptionId.isNotEmpty()) {
                onCancelledStartOver(
                    subscriptionId
                )
            } else {
                onBack()
            }
        }
    }

    LaunchedEffect(state) {
        val error =
            state as? FollowUpUiState.Error

        if (error?.httpStatus == 401) {
            onAuthExpired()
        }
    }

    LaunchedEffect(viewModel) {
        viewModel.navigationEvents
            .collect { event ->
                when (event) {
                    is FollowUpNavigationEvent
                        .OpenGuidance ->
                        onOpenGuidance(
                            event.snapshot
                        )
                }
            }
    }

    val snapshot =
        state.snapshotOrNull()

    val blockFollowUpInteraction =
        cancelState is CancelInquiryUiState.Cancelling ||
            cancelState is CancelInquiryUiState.Conflict ||
            cancelState is CancelInquiryUiState.Success

    PullToRefreshBox(
        isRefreshing = refreshing,
        onRefresh = {
            if (
                !blockFollowUpInteraction &&
                state !is FollowUpUiState.Loading &&
                state !is FollowUpUiState.Submitting
            ) {
                // 작성 중인 답변은 유지하고
                // Backend의 최신 질문과 workflow 상태만 다시 확인한다.
                viewModel.refresh()
            }
        },
    ) {
        WaterCareScreen(
            title = "추가 질문",
            onBack = onBack,
        ) {
            if (state is FollowUpUiState.Loading) {
                // 첫 조회에서 아무 내용도 없는 화면을 보여주지 않는다.
                CustomerInitialLoadingState(
                    title =
                        "추가 질문을 확인하고 있어요",
                    message =
                        "현재 문의 상태와 필요한 추가 질문을 불러오고 있어요.",
                )
            }

            FollowUpCancelSection(
                snapshot = snapshot,
                cancelState = cancelState,
                onConfirmCancel = { stateVersion ->
                    viewModel.cancelInquiry(
                        stateVersion = stateVersion,
                        reasonCode = "CUSTOMER_REQUEST",
                    )
                },
                onRetryConflict =
                    viewModel::retryCancelAfterConflict,
                onRetryFailure = { stateVersion ->
                    viewModel.cancelInquiry(
                        stateVersion = stateVersion,
                        reasonCode = "CUSTOMER_REQUEST",
                    )
                },
                onReloadLatest =
                    viewModel::load,
                onCancelledDone = {
                    val subscriptionId =
                        snapshot
                            ?.subscriptionId
                            .orEmpty()
                            .trim()

                    if (subscriptionId.isNotEmpty()) {
                        onCancelledStartOver(
                            subscriptionId
                        )
                    } else {
                        onBack()
                    }
                },
            )

            if (
                state is FollowUpUiState.Empty &&
                snapshot?.statusCode
                    ?.trim()
                    ?.uppercase() ==
                    "QUESTIONNAIRE_IN_PROGRESS"
            ) {
                // 답변은 모두 저장됐지만 Backend가
                // 다음 workflow 상태로 전환하는 중일 수 있다.
                // 이 순간을 Empty로 보여주면
                // "질문이 사라졌다"고 오해할 수 있어 처리 중으로 표시한다.
                CustomerInitialLoadingState(
                    title =
                        "다음 단계를 준비하고 있어요",
                    message =
                        "답변을 확인했어요. 맞춤 안내를 준비하고 있어요.",
                )
            }

            if (!blockFollowUpInteraction) {
                FollowUpQuestionsSection(
                    state = state,
                    onTextChange =
                        viewModel::updateText,
                    onSelectOption =
                        viewModel::selectOption,
                    onSubmit =
                        viewModel::submitAnswers,
                    onRetryConflict =
                        viewModel::retryAfterConflict,
                    onReload =
                        viewModel::load,
                )
            }
        }
    }

}
