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


    // APP_WIDE_REFRESH_FOLLOWUP
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
        isRefreshing =
            state is FollowUpUiState.Loading,
        onRefresh = viewModel::load,
    ) {
        WaterCareScreen(
            title = "추가 질문",
            onBack = onBack,
        ) {
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
                // Visible loading UI intentionally hidden.
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
