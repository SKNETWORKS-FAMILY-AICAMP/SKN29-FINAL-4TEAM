package com.skn29.watercare.customer.feature.customer.guidance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquiryQuestion
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.repository.CustomerInquiryRepository
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch

sealed interface FollowUpNavigationEvent {
    data class OpenGuidance(
        val snapshot: CustomerInquirySnapshot,
    ) : FollowUpNavigationEvent
}

class FollowUpQuestionsViewModel(
    private val inquiryId: String,
    private val repository: CustomerInquiryRepository,
) : ViewModel() {
    private val _state =
        MutableStateFlow<FollowUpUiState>(
            FollowUpUiState.Loading
        )

    val state: StateFlow<FollowUpUiState> =
        _state.asStateFlow()

    private val navigationChannel =
        Channel<FollowUpNavigationEvent>(
            capacity = Channel.BUFFERED,
        )

    val navigationEvents =
        navigationChannel.receiveAsFlow()

    init {
        load()
    }

    fun load() {
        val drafts =
            contextOrNull(_state.value)
                ?.drafts
                .orEmpty()

        viewModelScope.launch {
            _state.value =
                FollowUpUiState.Loading

            when (
                val result =
                    fetchContext(
                        preservedDrafts = drafts,
                    )
            ) {
                is ApiResult.Success ->
                    applyLoadedContext(
                        context = result.value,
                    )

                is ApiResult.Failure ->
                    _state.value =
                        failureState(
                            failure = result,
                            previous = null,
                        )
            }
        }
    }

    fun updateText(
        questionId: String,
        value: String,
    ) {
        editDraft(questionId) {
            it.copy(
                text = value,
                selectedOption = null,
            )
        }
    }

    fun selectOption(
        questionId: String,
        value: String,
    ) {
        editDraft(questionId) {
            it.copy(
                text = "",
                selectedOption = value,
            )
        }
    }

    fun submitAnswers() {
        val current = _state.value

        if (
            current is FollowUpUiState.Loading ||
            current is FollowUpUiState.Submitting ||
            current is FollowUpUiState.Disabled ||
            current is FollowUpUiState.Empty ||
            current is FollowUpUiState.Conflict ||
            current is FollowUpUiState.DuplicateConflict
        ) {
            return
        }

        val context =
            contextOrNull(current)
                ?: return

        submit(context)
    }

    fun retryAfterConflict() {
        val current =
            _state.value as?
                FollowUpUiState.Conflict
                ?: return

        if (!current.canRetry) {
            return
        }

        submit(
            FollowUpContext(
                snapshot = current.snapshot,
                questions = current.questions,
                drafts = current.drafts,
            )
        )
    }

    private fun editDraft(
        questionId: String,
        transform: (FollowUpDraft) -> FollowUpDraft,
    ) {
        val current = _state.value

        if (current is FollowUpUiState.Submitting) {
            return
        }

        val context =
            contextOrNull(current)
                ?: return

        if (
            context.questions.none {
                it.questionId == questionId
            }
        ) {
            return
        }

        val before =
            context.drafts[questionId]
                ?: FollowUpDraft()

        val after =
            transform(before)

        if (before == after) {
            return
        }

        val updated =
            context.drafts +
                (questionId to after)

        _state.value =
            when (current) {
                is FollowUpUiState.Conflict ->
                    current.copy(
                        drafts = updated,
                    )

                is FollowUpUiState.DuplicateConflict ->
                    FollowUpUiState.Form(
                        snapshot = current.snapshot,
                        questions = current.questions,
                        drafts = updated,
                    )

                else ->
                    FollowUpUiState.Form(
                        snapshot = context.snapshot,
                        questions = context.questions,
                        drafts = updated,
                    )
            }
    }

    private fun submit(
        context: FollowUpContext,
    ) {
        val submitAllowed =
            context.snapshot.allowedActions.any {
                it.normalizedCode ==
                    InquiryActionLabels.SUBMIT_ANSWERS
            }

        if (!submitAllowed) {
            _state.value =
                FollowUpUiState.Error(
                    message =
                        "현재 문의 상태에서는 추가 답변을 제출할 수 없습니다.",
                    code = "ACTION_NOT_ALLOWED",
                    httpStatus = null,
                    retryable = false,
                    snapshot = context.snapshot,
                    questions = context.questions,
                    drafts = context.drafts,
                )
            return
        }

        val answers =
            buildAnswers(context)

        if (answers == null) {
            _state.value =
                FollowUpUiState.Error(
                    message =
                        "모든 필수 추가 질문에 답변해 주세요.",
                    code = "CLIENT_VALIDATION_ERROR",
                    httpStatus = null,
                    retryable = false,
                    snapshot = context.snapshot,
                    questions = context.questions,
                    drafts = context.drafts,
                )
            return
        }

        viewModelScope.launch {
            _state.value =
                FollowUpUiState.Submitting(
                    snapshot = context.snapshot,
                    questions = context.questions,
                    drafts = context.drafts,
                )

            when (
                val result =
                    repository.submitAnswers(
                        inquiryId = inquiryId,
                        stateVersion =
                            context.snapshot.stateVersion,
                        answers = answers,
                    )
            ) {
                is ApiResult.Success ->
                    applySubmitSuccess(
                        result.value,
                    )

                is ApiResult.Failure ->
                    applySubmitFailure(
                        failure = result,
                        previous = context,
                    )
            }
        }
    }

    private suspend fun applySubmitSuccess(
        result: SubmitFollowUpAnswersResult,
    ) {
        when (
            val refreshed =
                fetchContext(
                    preservedDrafts =
                        emptyMap(),
                )
        ) {
            is ApiResult.Success -> {
                val context =
                    refreshed.value

                _state.value =
                    FollowUpUiState.Success(
                        snapshot = context.snapshot,
                        questions = context.questions,
                        drafts = context.drafts,
                        message = result.message,
                        idempotentReplay =
                            result.idempotentReplay,
                    )

                if (context.questions.isEmpty()) {
                    navigationChannel.send(
                        FollowUpNavigationEvent
                            .OpenGuidance(
                                context.snapshot
                            )
                    )
                }
            }

            is ApiResult.Failure ->
                _state.value =
                    failureState(
                        failure = refreshed,
                        previous = null,
                    )
        }
    }

    private suspend fun applySubmitFailure(
        failure: ApiResult.Failure,
        previous: FollowUpContext,
    ) {
        when {
            failure.code ==
                "STATE-CONFLICT-01" -> {
                when (
                    val refreshed =
                        fetchContext(
                            preservedDrafts =
                                previous.drafts,
                        )
                ) {
                    is ApiResult.Success -> {
                        val latest =
                            refreshed.value

                        if (
                            latest.questions
                                .isEmpty()
                        ) {
                            _state.value =
                                FollowUpUiState.Empty(
                                    latest.snapshot
                                )

                            navigationChannel.send(
                                FollowUpNavigationEvent
                                    .OpenGuidance(
                                        latest.snapshot
                                    )
                            )
                        } else {
                            _state.value =
                                FollowUpUiState.Conflict(
                                    message =
                                        failure.message,
                                    snapshot =
                                        latest.snapshot,
                                    questions =
                                        latest.questions,
                                    drafts =
                                        latest.drafts,
                                )
                        }
                    }

                    is ApiResult.Failure ->
                        _state.value =
                            failureState(
                                failure =
                                    refreshed,
                                previous =
                                    previous,
                            )
                }
            }

            failure.code ==
                "DUPLICATE-EVENT-01" ->
                _state.value =
                    FollowUpUiState
                        .DuplicateConflict(
                            message =
                                failure.message,
                            snapshot =
                                previous.snapshot,
                            questions =
                                previous.questions,
                            drafts =
                                previous.drafts,
                        )

            else ->
                _state.value =
                    failureState(
                        failure = failure,
                        previous = previous,
                    )
        }
    }

    private suspend fun fetchContext(
        preservedDrafts:
            Map<String, FollowUpDraft>,
    ): ApiResult<FollowUpContext> {
        val snapshot =
            when (
                val result =
                    repository.snapshot(
                        inquiryId
                    )
            ) {
                is ApiResult.Success ->
                    result.value

                is ApiResult.Failure ->
                    return result
            }

        val questionData =
            when (
                val result =
                    repository.questions(
                        inquiryId
                    )
            ) {
                is ApiResult.Success ->
                    result.value

                is ApiResult.Failure ->
                    return result
            }

        if (
            snapshot.inquiryId !=
                questionData.inquiryId ||
            snapshot.inquiryId != inquiryId
        ) {
            return ApiResult.Failure(
                code =
                    "CUSTOMER_INQUIRY_CONTRACT_MISMATCH",
                message =
                    "문의 조회 응답의 식별자가 일치하지 않습니다.",
                retryable = true,
            )
        }

        val consistentSnapshot =
            if (
                snapshot.stateVersion ==
                    questionData.stateVersion
            ) {
                snapshot
            } else {
                when (
                    val refreshed =
                        repository.snapshot(
                            inquiryId
                        )
                ) {
                    is ApiResult.Success -> {
                        if (
                            refreshed.value
                                .stateVersion !=
                            questionData
                                .stateVersion
                        ) {
                            return ApiResult.Failure(
                                code =
                                    "INQUIRY_CHANGED_DURING_LOAD",
                                message =
                                    "문의 상태가 갱신되었습니다. 최신 질문을 다시 확인해 주세요.",
                                retryable = true,
                            )
                        }

                        refreshed.value
                    }

                    is ApiResult.Failure ->
                        return refreshed
                }
            }

        val drafts =
            questionData.questions.associate {
                question ->
                question.questionId to
                    (
                        preservedDrafts[
                            question.questionId
                        ] ?: FollowUpDraft()
                    )
            }

        return ApiResult.Success(
            FollowUpContext(
                snapshot =
                    consistentSnapshot,
                questions =
                    questionData.questions,
                drafts = drafts,
            )
        )
    }

    private suspend fun applyLoadedContext(
        context: FollowUpContext,
    ) {
        if (context.questions.isEmpty()) {
            _state.value =
                FollowUpUiState.Empty(
                    context.snapshot
                )

            navigationChannel.send(
                FollowUpNavigationEvent
                    .OpenGuidance(
                        context.snapshot
                    )
            )
        } else {
            _state.value =
                FollowUpUiState.Form(
                    snapshot =
                        context.snapshot,
                    questions =
                        context.questions,
                    drafts =
                        context.drafts,
                )
        }
    }

    private fun failureState(
        failure: ApiResult.Failure,
        previous: FollowUpContext?,
    ): FollowUpUiState.Error {
        val mayKeepInput =
            failure.httpStatus !in
                setOf(401, 403, 404)

        return FollowUpUiState.Error(
            message = failure.message,
            code = failure.code,
            httpStatus =
                failure.httpStatus,
            retryable =
                failure.retryable,
            snapshot =
                if (mayKeepInput) {
                    previous?.snapshot
                } else {
                    null
                },
            questions =
                if (mayKeepInput) {
                    previous?.questions
                        .orEmpty()
                } else {
                    emptyList()
                },
            drafts =
                if (mayKeepInput) {
                    previous?.drafts
                        .orEmpty()
                } else {
                    emptyMap()
                },
        )
    }

    private fun buildAnswers(
        context: FollowUpContext,
    ): List<FollowUpAnswer>? {
        if (context.questions.isEmpty()) {
            return null
        }

        val answers =
            mutableListOf<FollowUpAnswer>()

        for (
            question in
                context.questions
        ) {
            val draft =
                context.drafts[
                    question.questionId
                ] ?: FollowUpDraft()

            val answer =
                when {
                    question.isFreeText -> {
                        val value =
                            draft.text.trim()

                        if (
                            value.isBlank()
                        ) {
                            if (
                                question.required
                            ) {
                                return null
                            }

                            continue
                        }

                        FollowUpAnswer(
                            questionId =
                                question.questionId,
                            answerText =
                                value,
                        )
                    }

                    question
                        .isSingleChoice -> {
                        val value =
                            draft.selectedOption
                                ?.trim()
                                ?.takeIf(
                                    String::isNotEmpty
                                )

                        if (value == null) {
                            if (
                                question.required
                            ) {
                                return null
                            }

                            continue
                        }

                        if (
                            question.options.none {
                                it.value == value
                            }
                        ) {
                            return null
                        }

                        FollowUpAnswer(
                            questionId =
                                question.questionId,
                            selectedOption =
                                value,
                        )
                    }

                    else ->
                        return null
                }

            answers += answer
        }

        if (answers.isEmpty()) {
            return null
        }

        return answers
    }

    private fun contextOrNull(
        state: FollowUpUiState,
    ): FollowUpContext? =
        when (state) {
            is FollowUpUiState.Form ->
                FollowUpContext(
                    state.snapshot,
                    state.questions,
                    state.drafts,
                )

            is FollowUpUiState.Submitting ->
                FollowUpContext(
                    state.snapshot,
                    state.questions,
                    state.drafts,
                )

            is FollowUpUiState.Success ->
                FollowUpContext(
                    state.snapshot,
                    state.questions,
                    state.drafts,
                )

            is FollowUpUiState.Conflict ->
                FollowUpContext(
                    state.snapshot,
                    state.questions,
                    state.drafts,
                )

            is FollowUpUiState.DuplicateConflict ->
                FollowUpContext(
                    state.snapshot,
                    state.questions,
                    state.drafts,
                )

            is FollowUpUiState.Error ->
                state.snapshot?.let {
                    FollowUpContext(
                        it,
                        state.questions,
                        state.drafts,
                    )
                }

            FollowUpUiState.Disabled,
            FollowUpUiState.Loading,
            is FollowUpUiState.Empty ->
                null
        }

    private data class FollowUpContext(
        val snapshot:
            CustomerInquirySnapshot,
        val questions:
            List<CustomerInquiryQuestion>,
        val drafts:
            Map<String, FollowUpDraft>,
    )
}