package com.skn29.watercare.customer.feature.customer.intake

import com.skn29.watercare.core.model.EntryMode
import com.skn29.watercare.core.model.IntakeSubmission
import com.skn29.watercare.core.model.MockScenario
import com.skn29.watercare.core.model.SymptomTopic

enum class IntakeErrorKind(val displayName: String) {
    VALIDATION("입력 확인"),
    AUTH_EXPIRED("로그인 만료"),
    FORBIDDEN("권한 부족"),
    NOT_FOUND("정보 없음"),
    CONFLICT("상태 충돌"),
    SERVER("서버 오류"),
    NETWORK("네트워크 오류"),
    UNKNOWN("처리 오류"),
}

data class SymptomIntakeUiState(
    val selectedSymptoms: Set<SymptomTopic> = emptySet(),
    val rawText: String = "",
    val occurrenceCondition: String = "",
    val displayText: String = "",
    val entryMode: EntryMode = EntryMode.ADHOC_INQUIRY,
    val forcedScenario: MockScenario? = null,
    val isSubmitting: Boolean = false,
    val rawTextError: String? = null,
    val globalError: String? = null,
    val errorKind: IntakeErrorKind? = null,
    val retryable: Boolean = false,
    val conflictStatus: String? = null,
    val conflictStateVersion: Int? = null,
    val conflictAllowedActions: List<String> = emptyList(),
    val completed: IntakeSubmission? = null,
)
