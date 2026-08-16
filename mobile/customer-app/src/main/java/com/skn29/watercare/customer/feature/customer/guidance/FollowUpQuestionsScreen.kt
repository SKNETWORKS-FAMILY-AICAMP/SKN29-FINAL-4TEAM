package com.skn29.watercare.customer.feature.customer.guidance

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
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
    onOpenGuidance:
        (CustomerInquirySnapshot) -> Unit,
) {
    val viewModel:
        FollowUpQuestionsViewModel =
        viewModel(
            factory =
                VmFactory { _ ->
                    FollowUpQuestionsViewModel(
                        inquiryId =
                            inquiryId,
                        repository =
                            WaterCareCore
                                .customerInquiryRepository,
                    )
                }
        )

    val state by
        viewModel.state
            .collectAsStateWithLifecycle()

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

    WaterCareScreen(
        title = "추가 질문",
        onBack = onBack,
    ) {
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