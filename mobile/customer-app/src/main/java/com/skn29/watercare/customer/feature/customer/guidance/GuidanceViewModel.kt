package com.skn29.watercare.customer.feature.customer.guidance

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.AllowedAction
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CustomerInquiryQuestion
import com.skn29.watercare.core.model.CustomerInquirySnapshot
import com.skn29.watercare.core.model.FollowUpAnswer
import com.skn29.watercare.core.model.GuidanceMapper
import com.skn29.watercare.core.model.InquiryActionLabels
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SubmitFollowUpAnswersResult
import com.skn29.watercare.core.repository.CustomerCareRepository
import com.skn29.watercare.core.repository.CustomerInquiryRepository
import com.skn29.watercare.core.repository.InquiryRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class GuidanceViewModel(
    private val inquiryId: String,
    private val scenario: MockScenario,
    private val repository: CustomerCareRepository,
    private val inquiryRepository: InquiryRepository? = null,
    private val customerInquiryRepository: CustomerInquiryRepository? = null,
    private val followUpEnabled: Boolean = false,
) : ViewModel() {
    private val _state = MutableStateFlow<GuidanceUiState>(GuidanceUiState.Loading)
    val state: StateFlow<GuidanceUiState> = _state.asStateFlow()

    private val _cancelState =
        MutableStateFlow<CancelInquiryUiState>(CancelInquiryUiState.Idle)
    val cancelState: StateFlow<CancelInquiryUiState> = _cancelState.asStateFlow()

    private val _followUpState = MutableStateFlow<FollowUpUiState>(
        if (followUpEnabled) FollowUpUiState.Loading else FollowUpUiState.Disabled
    )
    val followUpState: StateFlow<FollowUpUiState> = _followUpState.asStateFlow()

    private var lastCancelReasonCode: String = "CUSTOMER_REQUEST"
    private var lastCancelReasonDetail: String? = null

    init {
        load()
        if (followUpEnabled) loadFollowUp()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = GuidanceUiState.Loading
            _state.value = when (val result = repository.getGuidance(inquiryId, scenario)) {
                is ApiResult.Success -> {
                    val mapped = GuidanceMapper.map(result.value)
                    if (mapped.evidence.isEmpty()) GuidanceUiState.NoEvidence(mapped)
                    else GuidanceUiState.Content(mapped)
                }
                is ApiResult.Failure -> when {
                    result.code.startsWith("AI_") ->
                        GuidanceUiState.AiFailure(result.message, result.retryable)
                    result.code == "NETWORK_ERROR" ->
                        GuidanceUiState.NetworkFailure(result.message, result.retryable)
                    else -> GuidanceUiState.Error(result.message, result.retryable)
                }
            }
        }
    }

    fun loadFollowUp() {
        if (!followUpEnabled) {
            _followUpState.value = FollowUpUiState.Disabled
            return
        }
        val remote = customerInquiryRepository
        if (remote == null) {
            _followUpState.value = FollowUpUiState.Error(
                message = "고객 문의 조회 기능을 사용할 수 없습니다.",
                code = "CUSTOMER_INQUIRY_REPOSITORY_UNAVAILABLE",
                httpStatus = null,
                retryable = false,
            )
            return
        }
        val preservedDrafts = followUpContext(_followUpState.value)?.drafts.orEmpty()
        viewModelScope.launch {
            _followUpState.value = FollowUpUiState.Loading
            _followUpState.value = when (
                val loaded = fetchFollowUpContext(remote, preservedDrafts)
            ) {
                is ApiResult.Success -> loaded.value.toLoadedUiState()
                is ApiResult.Failure -> failureState(loaded, null)
            }
        }
    }

    fun retryFollowUpLoad() = loadFollowUp()

    fun updateFollowUpText(questionId: String, value: String) {
        editFollowUpDraft(questionId) { current ->
            current.copy(text = value, selectedOption = null)
        }
    }

    fun selectFollowUpOption(questionId: String, value: String) {
        editFollowUpDraft(questionId) { current ->
            current.copy(text = "", selectedOption = value)
        }
    }

    fun submitFollowUpAnswers() {
        val current = _followUpState.value
        if (
            current is FollowUpUiState.Loading ||
            current is FollowUpUiState.Submitting ||
            current is FollowUpUiState.Disabled ||
            current is FollowUpUiState.Empty ||
            current is FollowUpUiState.Conflict ||
            current is FollowUpUiState.DuplicateConflict
        ) return
        val context = followUpContext(current) ?: return
        performFollowUpSubmit(context)
    }

    fun retryFollowUpAfterConflict() {
        val current = _followUpState.value as? FollowUpUiState.Conflict ?: return
        if (!current.canRetry) return
        performFollowUpSubmit(
            FollowUpContext(current.snapshot, current.questions, current.drafts)
        )
    }

    private fun editFollowUpDraft(
        questionId: String,
        transform: (FollowUpDraft) -> FollowUpDraft,
    ) {
        val current = _followUpState.value
        if (current is FollowUpUiState.Submitting) return
        val context = followUpContext(current) ?: return
        if (context.questions.none { it.questionId == questionId }) return
        val before = context.drafts[questionId] ?: FollowUpDraft()
        val after = transform(before)
        if (before == after) return
        val updated = context.drafts + (questionId to after)
        _followUpState.value = when (current) {
            is FollowUpUiState.Conflict -> current.copy(drafts = updated)
            is FollowUpUiState.DuplicateConflict ->
                FollowUpUiState.Form(current.snapshot, current.questions, updated)
            else -> FollowUpUiState.Form(context.snapshot, context.questions, updated)
        }
    }

    private fun performFollowUpSubmit(context: FollowUpContext) {
        val remote = customerInquiryRepository ?: return
        val submitAllowed = context.snapshot.allowedActions.any {
            it.normalizedCode == InquiryActionLabels.SUBMIT_ANSWERS
        }
        if (!submitAllowed) {
            _followUpState.value = FollowUpUiState.Error(
                message = "현재 문의 상태에서는 추가 답변을 제출할 수 없습니다.",
                code = "ACTION_NOT_ALLOWED",
                httpStatus = null,
                retryable = false,
                snapshot = context.snapshot,
                questions = context.questions,
                drafts = context.drafts,
            )
            return
        }
        val answers = buildAnswers(context)
        if (answers == null) {
            _followUpState.value = FollowUpUiState.Error(
                message = "모든 필수 추가 질문에 답변해 주세요.",
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
            _followUpState.value = FollowUpUiState.Submitting(
                context.snapshot, context.questions, context.drafts
            )
            when (
                val result = remote.submitAnswers(
                    inquiryId = inquiryId,
                    stateVersion = context.snapshot.stateVersion,
                    answers = answers,
                )
            ) {
                is ApiResult.Success -> applyFollowUpSuccess(remote, result.value)
                is ApiResult.Failure -> applyFollowUpFailure(remote, result, context)
            }
        }
    }

    private suspend fun applyFollowUpSuccess(
        remote: CustomerInquiryRepository,
        result: SubmitFollowUpAnswersResult,
    ) {
        _followUpState.value = when (
            val refreshed = fetchFollowUpContext(remote, emptyMap())
        ) {
            is ApiResult.Success -> FollowUpUiState.Success(
                snapshot = refreshed.value.snapshot,
                questions = refreshed.value.questions,
                drafts = refreshed.value.drafts,
                message = result.message,
                idempotentReplay = result.idempotentReplay,
            )
            is ApiResult.Failure -> failureState(refreshed, null)
        }
    }

    private suspend fun applyFollowUpFailure(
        remote: CustomerInquiryRepository,
        failure: ApiResult.Failure,
        previous: FollowUpContext,
    ) {
        _followUpState.value = when {
            failure.code == "STATE-CONFLICT-01" -> {
                when (
                    val refreshed = fetchFollowUpContext(remote, previous.drafts)
                ) {
                    is ApiResult.Success -> FollowUpUiState.Conflict(
                        message = failure.message,
                        snapshot = refreshed.value.snapshot,
                        questions = refreshed.value.questions,
                        drafts = refreshed.value.drafts,
                    )
                    is ApiResult.Failure -> failureState(refreshed, previous)
                }
            }
            failure.code == "DUPLICATE-EVENT-01" ->
                FollowUpUiState.DuplicateConflict(
                    message = failure.message,
                    snapshot = previous.snapshot,
                    questions = previous.questions,
                    drafts = previous.drafts,
                )
            else -> failureState(failure, previous)
        }
    }

    private suspend fun fetchFollowUpContext(
        remote: CustomerInquiryRepository,
        preservedDrafts: Map<String, FollowUpDraft>,
    ): ApiResult<FollowUpContext> {
        val snapshot = when (val result = remote.snapshot(inquiryId)) {
            is ApiResult.Success -> result.value
            is ApiResult.Failure -> return result
        }
        val questionData = when (val result = remote.questions(inquiryId)) {
            is ApiResult.Success -> result.value
            is ApiResult.Failure -> return result
        }
        if (snapshot.inquiryId != questionData.inquiryId || snapshot.inquiryId != inquiryId) {
            return ApiResult.Failure(
                code = "CUSTOMER_INQUIRY_CONTRACT_MISMATCH",
                message = "문의 조회 응답의 식별자가 일치하지 않습니다.",
                retryable = true,
            )
        }
        val consistentSnapshot = if (snapshot.stateVersion == questionData.stateVersion) {
            snapshot
        } else {
            when (val refreshed = remote.snapshot(inquiryId)) {
                is ApiResult.Success -> {
                    if (refreshed.value.stateVersion != questionData.stateVersion) {
                        return ApiResult.Failure(
                            code = "INQUIRY_CHANGED_DURING_LOAD",
                            message = "문의 상태가 갱신되었습니다. 최신 질문을 다시 확인해 주세요.",
                            retryable = true,
                        )
                    }
                    refreshed.value
                }
                is ApiResult.Failure -> return refreshed
            }
        }
        val drafts = questionData.questions.associate { question ->
            question.questionId to (preservedDrafts[question.questionId] ?: FollowUpDraft())
        }
        return ApiResult.Success(
            FollowUpContext(consistentSnapshot, questionData.questions, drafts)
        )
    }

    private fun failureState(
        failure: ApiResult.Failure,
        previous: FollowUpContext?,
    ): FollowUpUiState.Error {
        val mayKeepInput = failure.httpStatus !in setOf(401, 403, 404)
        return FollowUpUiState.Error(
            message = failure.message,
            code = failure.code,
            httpStatus = failure.httpStatus,
            retryable = failure.retryable,
            snapshot = if (mayKeepInput) previous?.snapshot else null,
            questions = if (mayKeepInput) previous?.questions.orEmpty() else emptyList(),
            drafts = if (mayKeepInput) previous?.drafts.orEmpty() else emptyMap(),
        )
    }

    private fun buildAnswers(context: FollowUpContext): List<FollowUpAnswer>? {
        if (context.questions.isEmpty()) return null
        val answers = mutableListOf<FollowUpAnswer>()
        for (question in context.questions) {
            val draft = context.drafts[question.questionId] ?: FollowUpDraft()
            val answer = when {
                question.isFreeText -> {
                    val text = draft.text.trim()
                    if (text.isBlank()) return null
                    FollowUpAnswer(questionId = question.questionId, answerText = text)
                }
                question.isSingleChoice -> {
                    val option = draft.selectedOption?.trim()?.takeIf(String::isNotEmpty)
                        ?: return null
                    if (question.options.none { it.value == option }) return null
                    FollowUpAnswer(questionId = question.questionId, selectedOption = option)
                }
                else -> return null
            }
            answers += answer
        }
        return answers
    }

    fun cancelInquiry(
        stateVersion: Int?,
        reasonCode: String = "CUSTOMER_REQUEST",
        reasonDetail: String? = null,
    ) {
        val remote = inquiryRepository
        if (remote == null) {
            _cancelState.value = CancelInquiryUiState.Error(
                message = "문의 취소 기능을 사용할 수 없습니다.",
                retryable = false,
            )
            return
        }
        if (stateVersion == null || stateVersion < 1) {
            _cancelState.value = CancelInquiryUiState.Error(
                message = "최신 문의 상태 버전을 확인한 뒤 다시 시도해 주세요.",
                retryable = false,
            )
            return
        }
        lastCancelReasonCode = reasonCode
        lastCancelReasonDetail = reasonDetail
        performCancel(remote, stateVersion, reasonCode, reasonDetail)
    }

    fun retryCancelAfterConflict() {
        val current = _cancelState.value
        if (current !is CancelInquiryUiState.Conflict) return
        val latestVersion = current.currentStateVersion
        val canRetry = latestVersion != null && current.allowedActions.any {
            it.normalizedCode == InquiryActionLabels.CANCEL_INQUIRY
        }
        if (!canRetry) return
        val remote = inquiryRepository ?: return
        performCancel(remote, latestVersion, lastCancelReasonCode, lastCancelReasonDetail)
    }

    private fun performCancel(
        repository: InquiryRepository,
        stateVersion: Int,
        reasonCode: String,
        reasonDetail: String?,
    ) {
        viewModelScope.launch {
            _cancelState.value = CancelInquiryUiState.Cancelling
            _cancelState.value = when (
                val result = repository.cancel(
                    inquiryId = inquiryId,
                    stateVersion = stateVersion,
                    reasonCode = reasonCode,
                    reasonDetail = reasonDetail,
                )
            ) {
                is ApiResult.Success -> CancelInquiryUiState.Success(
                    state = result.value.state,
                    stateVersion = result.value.stateVersion,
                    idempotentReplay = result.value.idempotentReplay,
                )
                is ApiResult.Failure -> {
                    val conflict = result.conflict
                    if (conflict != null) {
                        CancelInquiryUiState.Conflict(
                            message = result.message,
                            currentStatus = conflict.currentStatus,
                            currentStateVersion = conflict.currentStateVersion,
                            allowedActions = conflict.allowedActions,
                        )
                    } else {
                        CancelInquiryUiState.Error(result.message, result.retryable)
                    }
                }
            }
        }
    }

    private data class FollowUpContext(
        val snapshot: CustomerInquirySnapshot,
        val questions: List<CustomerInquiryQuestion>,
        val drafts: Map<String, FollowUpDraft>,
    ) {
        fun toLoadedUiState(): FollowUpUiState = if (questions.isEmpty()) {
            FollowUpUiState.Empty(snapshot)
        } else {
            FollowUpUiState.Form(snapshot, questions, drafts)
        }
    }

    private fun followUpContext(state: FollowUpUiState): FollowUpContext? = when (state) {
        is FollowUpUiState.Form -> FollowUpContext(state.snapshot, state.questions, state.drafts)
        is FollowUpUiState.Submitting -> FollowUpContext(state.snapshot, state.questions, state.drafts)
        is FollowUpUiState.Success -> FollowUpContext(state.snapshot, state.questions, state.drafts)
        is FollowUpUiState.Conflict -> FollowUpContext(state.snapshot, state.questions, state.drafts)
        is FollowUpUiState.DuplicateConflict -> FollowUpContext(state.snapshot, state.questions, state.drafts)
        is FollowUpUiState.Error -> state.snapshot?.let {
            FollowUpContext(it, state.questions, state.drafts)
        }
        FollowUpUiState.Disabled, FollowUpUiState.Loading, is FollowUpUiState.Empty -> null
    }
}

sealed interface CancelInquiryUiState {
    data object Idle : CancelInquiryUiState
    data object Cancelling : CancelInquiryUiState

    data class Success(
        val state: String,
        val stateVersion: Int,
        val idempotentReplay: Boolean,
    ) : CancelInquiryUiState

    data class Conflict(
        val message: String,
        val currentStatus: String?,
        val currentStateVersion: Int?,
        val allowedActions: List<AllowedAction>,
    ) : CancelInquiryUiState {
        val canRetry: Boolean
            get() = currentStateVersion != null && allowedActions.any {
                it.normalizedCode == InquiryActionLabels.CANCEL_INQUIRY
            }
    }

    data class Error(
        val message: String,
        val retryable: Boolean,
    ) : CancelInquiryUiState
}
