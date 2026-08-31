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

    private val _workflowSnapshot =
        MutableStateFlow<CustomerWorkflowUiSnapshot?>(null)
    val workflowSnapshot:
        StateFlow<CustomerWorkflowUiSnapshot?> =
        _workflowSnapshot.asStateFlow()

    private val _authExpired =
        MutableStateFlow(false)
    val authExpired: StateFlow<Boolean> =
        _authExpired.asStateFlow()

    fun consumeAuthExpired() {
        _authExpired.value = false
    }
    private val cancelRuntime =
        InquiryCancelRuntime(
            inquiryId = inquiryId,
            repository = inquiryRepository,
            scope = viewModelScope,
            onAuthExpired = {
                _authExpired.value = true
            },
        )

    val cancelState: StateFlow<CancelInquiryUiState> =
        cancelRuntime.state

    private val _followUpState = MutableStateFlow<FollowUpUiState>(
        if (followUpEnabled) FollowUpUiState.Loading else FollowUpUiState.Disabled
    )
    val followUpState: StateFlow<FollowUpUiState> = _followUpState.asStateFlow()

    private val _consultationState =
        MutableStateFlow<ConsultationRequestUiState>(
            ConsultationRequestUiState.Idle
        )
    val consultationState:
        StateFlow<ConsultationRequestUiState> =
        _consultationState.asStateFlow()

    private val _refreshing =
        MutableStateFlow(false)

    val refreshing: StateFlow<Boolean> =
        _refreshing.asStateFlow()

    private var silentRefreshInProgress =
        false

    init {
        load()
        if (followUpEnabled) loadFollowUp()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = GuidanceUiState.Loading

            val remote = customerInquiryRepository

            // Follow-up path uses loadFollowUp() to manage its Snapshot.
            // Avoid duplicate Snapshot reads on the follow-up path.
            if (remote == null || followUpEnabled) {
                _state.value = loadGuidanceState()
                return@launch
            }

            when (
                val snapshotResult =
                    remote.snapshot(inquiryId)
            ) {
                is ApiResult.Failure -> {
                    registerAuthExpiry(snapshotResult)
                    _state.value =
                        when {
                            snapshotResult.code ==
                                "NETWORK_ERROR" ->
                                GuidanceUiState
                                    .NetworkFailure(
                                        snapshotResult.message,
                                        snapshotResult.retryable,
                                    )

                            else ->
                                GuidanceUiState.Error(
                                    snapshotResult.message,
                                    snapshotResult.retryable,
                                )
                        }
                }

                is ApiResult.Success -> {
                    val latest = snapshotResult.value
                    replaceWorkflowSnapshot(latest)

                    _state.value =
                        loadStateForSnapshot(
                            remote = remote,
                            snapshot = latest,
                        )
                }
            }
        }
    }

    fun refresh() {
        refreshSilently(
            showIndicator = true
        )
    }

    fun refreshSilently(
        showIndicator: Boolean = false,
    ) {
        if (silentRefreshInProgress) {
            return
        }

        val remote =
            customerInquiryRepository
                ?: return

        if (followUpEnabled) {
            return
        }

        silentRefreshInProgress = true

        if (showIndicator) {
            _refreshing.value = true
        }

        viewModelScope.launch {
            try {
                when (
                    val snapshotResult =
                        remote.snapshot(
                            inquiryId
                        )
                ) {
                    is ApiResult.Failure -> {
                        registerAuthExpiry(
                            snapshotResult
                        )
                    }

                    is ApiResult.Success -> {
                        val latest =
                            snapshotResult.value

                        replaceWorkflowSnapshot(
                            latest
                        )

                        _state.value =
                            loadStateForSnapshot(
                                remote = remote,
                                snapshot = latest,
                            )
                    }
                }
            } finally {
                if (showIndicator) {
                    _refreshing.value = false
                }

                silentRefreshInProgress =
                    false
            }
        }
    }

    // 서버 상태에 따라 호출 가능한 API가 다르므로
    // snapshot을 먼저 보고 다음 조회를 결정한다.
    //
    // COMPLETION_PENDING:
    //   상담이 끝나는 단계이므로 consultation-result를 조회한다.
    //
    // CONSULTATION_REQUIRED / CONSULTATION_IN_PROGRESS:
    //   아직 guidance를 조회하면 409가 날 수 있어
    //   snapshot만 유지하고 guidance API는 호출하지 않는다.
    //
    // 그 외 guidance 조회가 가능한 상태에서는
    // 기존 guidance 조회 로직을 사용한다.
    private suspend fun loadStateForSnapshot(
        remote: CustomerInquiryRepository,
        snapshot: CustomerInquirySnapshot,
    ): GuidanceUiState =
        when (
            snapshot.statusCode
                .trim()
                .uppercase()
        ) {
            "COMPLETION_PENDING" ->
                loadConsultationResultState(
                    remote
                )

            "CONSULTATION_REQUIRED",
            "CONSULTATION_IN_PROGRESS" ->
                GuidanceUiState.NotReady(
                    message =
                        "\uC0C1\uB2F4 \uC9C4\uD589 \uC0C1\uD0DC\uB97C " +
                            "\uD655\uC778\uD558\uACE0 \uC788\uC5B4\uC694.",
                )

            else ->
                loadGuidanceState()
        }

    private suspend fun loadConsultationResultState(
        remote: CustomerInquiryRepository,
    ): GuidanceUiState =
        when (
            val result =
                remote.consultationResult(inquiryId)
        ) {
            is ApiResult.Success -> {
                if (
                    result.value.inquiryId != inquiryId
                ) {
                    GuidanceUiState.Error(
                        message =
                            "상담 처리 결과의 문의 정보가 일치하지 않습니다.",
                        retryable = true,
                    )
                } else {
                    replaceWorkflowResult(
                        result.value
                    )
                    GuidanceUiState
                        .ConsultationResult(
                            result.value
                        )
                }
            }

            is ApiResult.Failure -> {
                registerAuthExpiry(result)

                when {
                    result.httpStatus == 409 ->
                        GuidanceUiState
                            .ConsultationResultNotReady(
                                result.message
                            )

                    result.code == "NETWORK_ERROR" ->
                        GuidanceUiState
                            .NetworkFailure(
                                result.message,
                                result.retryable,
                            )

                    else ->
                        GuidanceUiState.Error(
                            result.message,
                            result.retryable,
                        )
                }
            }
        }

    private suspend fun loadGuidanceState():
        GuidanceUiState =
        when (
            val result =
                repository.getGuidance(
                    inquiryId,
                    scenario,
                )
        ) {
            is ApiResult.Success -> {
                val mapped =
                    GuidanceMapper.map(
                        result.value
                    )

                if (
                    mapped.riskLevel ==
                    com.skn29.watercare.core
                        .model.RiskLevel.UNKNOWN
                ) {
                    GuidanceUiState
                        .NoEvidence(mapped)
                } else {
                    GuidanceUiState
                        .Content(mapped)
                }
            }

            is ApiResult.Failure ->
                when {
                    result.httpStatus == 401 -> {
                        _authExpired.value = true
                        GuidanceUiState.Error(
                            message =
                                "로그인이 만료되었습니다. 다시 로그인해 주세요.",
                            retryable = false,
                        )
                    }

                    result.code ==
                        "AI_GUIDANCE_NOT_READY" &&
                        result.httpStatus == 409 ->
                        GuidanceUiState
                            .NotReady(
                                result.message
                            )

                    result.code
                        .startsWith("AI_") ->
                        GuidanceUiState
                            .AiFailure(
                                result.message,
                                result.retryable,
                            )

                    result.code ==
                        "NETWORK_ERROR" ->
                        GuidanceUiState
                            .NetworkFailure(
                                result.message,
                                result.retryable,
                            )

                    else ->
                        GuidanceUiState.Error(
                            result.message,
                            result.retryable,
                        )
                }
        }

    private fun replaceWorkflowSnapshot(
        snapshot: CustomerInquirySnapshot,
    ) {
        _workflowSnapshot.value =
            snapshot.toWorkflowUiSnapshot()
    }

    private fun replaceWorkflowResult(
        result:
            com.skn29.watercare.core.model
                .CustomerInquiryConsultationResult,
    ) {
        _workflowSnapshot.value =
            result.toWorkflowUiSnapshot()
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

    fun requestConsultation() {
        if (
            _consultationState.value is
                ConsultationRequestUiState.Requesting
        ) {
            return
        }

        val remote = customerInquiryRepository
        if (remote == null) {
            _consultationState.value =
                ConsultationRequestUiState.Error(
                    message =
                        "상담 요청 기능을 사용할 수 없습니다.",
                    retryable = false,
                )
            return
        }

        _consultationState.value =
            ConsultationRequestUiState.Requesting

        viewModelScope.launch {
            when (
                val latest = remote.snapshot(inquiryId)
            ) {
                is ApiResult.Failure -> {
                    registerAuthExpiry(latest)
                    _consultationState.value =
                        ConsultationRequestUiState.Error(
                            message =
                                "상담 요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요.",
                            retryable = latest.retryable,
                        )
                }

                is ApiResult.Success -> {
                    val snapshot = latest.value
                    replaceFollowUpSnapshot(snapshot)

                    val allowed =
                        snapshot.allowedActions.any {
                            it.normalizedCode ==
                                InquiryActionLabels
                                    .REQUEST_CONSULTATION
                        }

                    if (!allowed) {
                        _consultationState.value =
                            ConsultationRequestUiState.Error(
                                message =
                                    "현재 문의 상태에서는 상담을 요청할 수 없습니다.",
                                retryable = false,
                            )
                    } else {
                        performConsultationRequest(
                            remote = remote,
                            snapshot = snapshot,
                        )
                    }
                }
            }
        }
    }

    fun retryConsultationRequest() =
        requestConsultation()

    fun retryConsultationAfterConflict() {
        val current =
            _consultationState.value
                as? ConsultationRequestUiState.Conflict
                ?: return

        if (!current.canRetry) {
            return
        }

        val remote = customerInquiryRepository
            ?: return

        _consultationState.value =
            ConsultationRequestUiState.Requesting

        viewModelScope.launch {
            performConsultationRequest(
                remote = remote,
                snapshot = current.snapshot,
            )
        }
    }

    private suspend fun performConsultationRequest(
        remote: CustomerInquiryRepository,
        snapshot: CustomerInquirySnapshot,
    ) {
        when (
            val result = remote.requestConsultation(
                inquiryId = inquiryId,
                stateVersion = snapshot.stateVersion,
            )
        ) {
            is ApiResult.Success -> {
                applyConsultationSuccess(
                    remote = remote,
                    result = result.value,
                )
            }

            is ApiResult.Failure -> {
                applyConsultationFailure(
                    remote = remote,
                    failure = result,
                )
            }
        }
    }

    private suspend fun applyConsultationSuccess(
        remote: CustomerInquiryRepository,
        result:
            com.skn29.watercare.core.model.RequestConsultationResult,
    ) {
        if (result.inquiryId != inquiryId) {
            _consultationState.value =
                ConsultationRequestUiState.Error(
                    message =
                        "상담 요청 응답의 문의 정보가 일치하지 않습니다.",
                    retryable = true,
                )
            return
        }

        when (
            val refreshed = remote.snapshot(inquiryId)
        ) {
            is ApiResult.Failure -> {
                _consultationState.value =
                    ConsultationRequestUiState.Error(
                        message =
                            "상담 요청은 처리됐지만 최신 상태를 다시 확인하지 못했습니다. " +
                                refreshed.message,
                        retryable = refreshed.retryable,
                    )
            }

            is ApiResult.Success -> {
                val latest = refreshed.value
                replaceFollowUpSnapshot(latest)
                replaceWorkflowSnapshot(latest)

                _consultationState.value =
                    ConsultationRequestUiState.Success(
                        message = result.message,
                        snapshot = latest,
                        idempotentReplay =
                            result.idempotentReplay,
                    )
            }
        }
    }

    private suspend fun applyConsultationFailure(
        remote: CustomerInquiryRepository,
        failure: ApiResult.Failure,
    ) {
        val shouldRefresh =
            failure.httpStatus == 409 ||
                failure.conflict != null ||
                failure.code == "DUPLICATE-EVENT-01"

        if (!shouldRefresh) {
            registerAuthExpiry(failure)
            _consultationState.value =
                ConsultationRequestUiState.Error(
                    message =
                        "상담 요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요.",
                    retryable = failure.retryable,
                )
            return
        }

        when (
            val refreshed = remote.snapshot(inquiryId)
        ) {
            is ApiResult.Failure -> {
                _consultationState.value =
                    ConsultationRequestUiState.Error(
                        message = refreshed.message,
                        retryable = refreshed.retryable,
                    )
            }

            is ApiResult.Success -> {
                val latest = refreshed.value
                replaceFollowUpSnapshot(latest)
                replaceWorkflowSnapshot(latest)

                if (
                    failure.code ==
                        "DUPLICATE-EVENT-01" &&
                    latest.statusCode in setOf(
                        "CONSULTATION_REQUIRED",
                        "CONSULTATION_IN_PROGRESS",
                    )
                ) {
                    _consultationState.value =
                        ConsultationRequestUiState.Success(
                            message =
                                "이미 접수된 상담 요청의 최신 상태를 확인했습니다.",
                            snapshot = latest,
                            idempotentReplay = true,
                        )
                } else {
                    _consultationState.value =
                        ConsultationRequestUiState.Conflict(
                            message = failure.message,
                            snapshot = latest,
                        )
                }
            }
        }
    }

    private fun registerAuthExpiry(
        failure: ApiResult.Failure,
    ): Boolean {
        if (failure.httpStatus != 401) {
            return false
        }

        _authExpired.value = true
        return true
    }
    private fun replaceFollowUpSnapshot(
        snapshot: CustomerInquirySnapshot,
    ) {
        _followUpState.value =
            when (val current = _followUpState.value) {
                is FollowUpUiState.Empty ->
                    current.copy(snapshot = snapshot)

                is FollowUpUiState.Form ->
                    current.copy(snapshot = snapshot)

                is FollowUpUiState.Submitting ->
                    current.copy(snapshot = snapshot)

                is FollowUpUiState.Success ->
                    current.copy(snapshot = snapshot)

                is FollowUpUiState.Conflict ->
                    current.copy(snapshot = snapshot)

                is FollowUpUiState.DuplicateConflict ->
                    current.copy(snapshot = snapshot)

                is FollowUpUiState.Error ->
                    current.copy(snapshot = snapshot)

                FollowUpUiState.Disabled,
                FollowUpUiState.Loading ->
                    current
            }
    }

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
        cancelRuntime.cancelInquiry(
            stateVersion = stateVersion,
            reasonCode = reasonCode,
            reasonDetail = reasonDetail,
        )
    }

    fun retryCancelAfterConflict() {
        cancelRuntime.retryAfterConflict()
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
            get() =
                canCancelInquiry(
                    statusCode = currentStatus,
                    stateVersion = currentStateVersion,
                    allowedActions = allowedActions,
                )
    }

    data class Error(
        val message: String,
        val retryable: Boolean,
    ) : CancelInquiryUiState
}
