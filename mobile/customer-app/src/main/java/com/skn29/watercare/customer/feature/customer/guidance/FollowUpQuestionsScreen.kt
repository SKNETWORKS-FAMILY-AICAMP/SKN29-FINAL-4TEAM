package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.skn29.watercare.core.WaterCareCore
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.customer.common.VmFactory
import com.skn29.watercare.customer.feature.shared.WaterCareScreen
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.delay

@Composable
fun FollowUpQuestionsScreen(
    inquiryId: String,
    onBack: () -> Unit,
    onAuthExpired: () -> Unit = {},
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


    var processingRefreshCount by
        remember(inquiryId) {
            mutableIntStateOf(0)
        }

    LaunchedEffect(state) {
        val empty =
            state as? FollowUpUiState.Empty
        val waiting =
            empty?.snapshot
                ?.statusCode
                ?.trim()
                ?.uppercase() ==
                "QUESTIONNAIRE_IN_PROGRESS"

        if (
            waiting &&
            processingRefreshCount < 15
        ) {
            delay(2_000)
            processingRefreshCount += 1
            viewModel.load()
        } else if (
            !waiting &&
            state !is FollowUpUiState.Loading
        ) {
            processingRefreshCount = 0
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
            onCancelledDone =
                onBack,
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
