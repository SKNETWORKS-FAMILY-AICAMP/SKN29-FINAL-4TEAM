package com.skn29.watercare.customer.feature.customer.care

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.skn29.watercare.core.model.ApiResult
import com.skn29.watercare.core.model.CarePrecheckSessionDto
import com.skn29.watercare.core.repository.CarePrecheckRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive

data class CarePrecheckUiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val session: CarePrecheckSessionDto? = null,
    val waterFlow: String? = null,
    val leak: Boolean? = null,
    val saving: Boolean = false,
    val submitting: Boolean = false,
    val notice: String? = null,
    val error: String? = null,
    val retryable: Boolean = false,
    val authExpired: Boolean = false,
)

class CarePrecheckViewModel(
    private val subscriptionId: String,
    private val repository: CarePrecheckRepository,
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {
    private val _state =
        MutableStateFlow(CarePrecheckUiState())
    val state: StateFlow<CarePrecheckUiState> =
        _state.asStateFlow()

    init {
        loadOrStart()
    }

    fun consumeAuthExpired() {
        _state.value =
            _state.value.copy(authExpired = false)
    }

    fun selectWaterFlow(value: String) {
        _state.value =
            _state.value.copy(
                waterFlow = value,
                notice = null,
                error = null,
            )
    }

    fun selectLeak(value: Boolean) {
        _state.value =
            _state.value.copy(
                leak = value,
                notice = null,
                error = null,
            )
    }

    fun retry() = loadOrStart()

    fun refresh() {
        val current = _state.value

        if (
            current.loading ||
            current.refreshing ||
            current.saving ||
            current.submitting
        ) {
            return
        }

        val sessionId =
            current.session
                ?.questionnaireSessionId
                ?: savedStateHandle
                    .get<String>(
                        SESSION_ID_KEY
                    )
                    ?.takeIf(
                        String::isNotBlank
                    )

        if (sessionId == null) {
            loadOrStart()
            return
        }

        // Pull-to-refresh에서는 작성 중인 답변과 폼을 유지한다.
        // 전체 Loading 상태로 되돌아가지 않고 indicator만 표시한다.
        _state.value =
            current.copy(
                refreshing = true,
                error = null,
                retryable = false,
            )

        viewModelScope.launch {
            when (
                val result =
                    repository.get(
                        sessionId
                    )
            ) {
                is ApiResult.Success -> {
                    val latest =
                        result.value

                    val latestFlow =
                        latest.answers["WATER_FLOW"]
                            ?.jsonPrimitive
                            ?.contentOrNull

                    val latestLeak =
                        latest.answers["LEAK"]
                            ?.jsonPrimitive
                            ?.booleanOrNull

                    val submitted =
                        latest.statusCode ==
                            "SUBMITTED"

                    // Pull-to-refresh 중에는 아직 저장하지 않은
                    // 고객 입력을 서버의 이전 값으로 덮어쓰지 않는다.
                    //
                    // 다만 Backend에서 이미 SUBMITTED로 확정된 경우에는
                    // 서버 값을 최종 기준으로 다시 표시한다.
                    _state.value =
                        current.copy(
                            loading = false,
                            refreshing = false,
                            session = latest,
                            waterFlow =
                                if (submitted) {
                                    latestFlow
                                } else {
                                    current.waterFlow
                                        ?: latestFlow
                                },
                            leak =
                                if (submitted) {
                                    latestLeak
                                } else {
                                    current.leak
                                        ?: latestLeak
                                },
                            error = null,
                            retryable = false,
                            authExpired = false,
                        )
                }

                is ApiResult.Failure ->
                    applyFailure(
                        result
                    )
            }
        }
    }

    fun save() {
        val current = _state.value
        val session = current.session ?: return
        if (current.saving || current.submitting) return

        val answers =
            buildAnswers(
                current.waterFlow,
                current.leak,
            )

        if (answers.isEmpty()) {
            _state.value =
                current.copy(
                    error =
                        "한 가지 이상 확인한 뒤 저장해주세요.",
                    retryable = false,
                )
            return
        }

        _state.value =
            current.copy(
                saving = true,
                error = null,
                notice = null,
            )

        viewModelScope.launch {
            when (
                val result =
                    repository.save(
                        session.questionnaireSessionId,
                        session.stateVersion,
                        answers,
                    )
            ) {
                is ApiResult.Success ->
                    applySession(
                        result.value,
                        "작성한 사전 점검 내용을 저장했어요.",
                    )
                is ApiResult.Failure ->
                    applyFailure(result)
            }
        }
    }

    fun submit() {
        val current = _state.value
        val session = current.session ?: return
        if (
            current.saving ||
            current.submitting ||
            session.statusCode == "SUBMITTED"
        ) return

        if (
            current.waterFlow == null ||
            current.leak == null
        ) {
            _state.value =
                current.copy(
                    error =
                        "두 항목을 모두 확인해주세요.",
                    retryable = false,
                )
            return
        }

        val answers =
            buildAnswers(
                current.waterFlow,
                current.leak,
            )

        _state.value =
            current.copy(
                submitting = true,
                error = null,
                notice = null,
            )

        viewModelScope.launch {
            when (
                val result =
                    repository.submit(
                        session.questionnaireSessionId,
                        session.stateVersion,
                        answers,
                    )
            ) {
                is ApiResult.Success ->
                    applySession(
                        result.value,
                        "방문 전 사전 점검을 제출했어요.",
                    )
                is ApiResult.Failure ->
                    applyFailure(result)
            }
        }
    }

    private fun loadOrStart() {
        val existing =
            savedStateHandle
                .get<String>(SESSION_ID_KEY)
                ?.takeIf(String::isNotBlank)

        _state.value =
            _state.value.copy(
                loading = true,
                refreshing = false,
                error = null,
            )

        viewModelScope.launch {
            val result =
                if (existing == null) {
                    repository.start(subscriptionId)
                } else {
                    repository.get(existing)
                }

            when (result) {
                is ApiResult.Success -> {
                    savedStateHandle[
                        SESSION_ID_KEY
                    ] =
                        result.value
                            .questionnaireSessionId
                    applySession(result.value)
                }
                is ApiResult.Failure ->
                    applyFailure(result)
            }
        }
    }

    private fun applySession(
        session: CarePrecheckSessionDto,
        notice: String? = null,
    ) {
        val flow =
            session.answers["WATER_FLOW"]
                ?.jsonPrimitive
                ?.contentOrNull
        val leak =
            session.answers["LEAK"]
                ?.jsonPrimitive
                ?.booleanOrNull

        _state.value =
            CarePrecheckUiState(
                loading = false,
                refreshing = false,
                session = session,
                waterFlow =
                    flow ?: _state.value.waterFlow,
                leak =
                    leak ?: _state.value.leak,
                notice = notice,
            )
    }

    private fun applyFailure(
        failure: ApiResult.Failure,
    ) {
        val auth =
            failure.httpStatus == 401

        _state.value =
            _state.value.copy(
                loading = false,
                refreshing = false,
                saving = false,
                submitting = false,
                error =
                    when {
                        auth ->
                            "로그인이 만료됐어요. 다시 로그인해주세요."
                        failure.httpStatus == 409 ->
                            "사전 점검 상태가 변경됐어요. 다시 확인해주세요."
                        failure.code == "NETWORK_ERROR" ->
                            "인터넷 연결을 확인한 뒤 다시 시도해주세요."
                        else ->
                            "사전 점검을 처리하지 못했어요. 잠시 후 다시 시도해주세요."
                    },
                retryable =
                    failure.retryable ||
                        failure.httpStatus == 409,
                authExpired = auth,
            )
    }

    private fun buildAnswers(
        waterFlow: String?,
        leak: Boolean?,
    ) =
        buildJsonObject {
            waterFlow?.let {
                put(
                    "WATER_FLOW",
                    JsonPrimitive(it),
                )
            }
            leak?.let {
                put(
                    "LEAK",
                    JsonPrimitive(it),
                )
            }
        }

    companion object {
        private const val SESSION_ID_KEY =
            "care_precheck.session_id"
    }
}
