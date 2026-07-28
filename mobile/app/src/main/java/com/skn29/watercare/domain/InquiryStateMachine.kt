package com.skn29.watercare.domain

import com.skn29.watercare.model.InquiryState

sealed interface InquiryEvent {
    data object StartInquiry : InquiryEvent
    data object StartQuestionnaire : InquiryEvent
    data object ConfirmError : InquiryEvent
    data object RequestVisit : InquiryEvent
    data object CompleteVisit : InquiryEvent
    data object CancelInquiry : InquiryEvent
}

object InquiryStateMachine {
    fun next(current: InquiryState?, event: InquiryEvent): InquiryState = when (event) {
        InquiryEvent.StartInquiry -> InquiryState.DRAFT
        InquiryEvent.StartQuestionnaire -> requireState(
            current,
            setOf(InquiryState.DRAFT, InquiryState.QUESTIONNAIRE_IN_PROGRESS),
            InquiryState.QUESTIONNAIRE_IN_PROGRESS
        )
        InquiryEvent.ConfirmError -> requireState(
            current,
            setOf(InquiryState.DRAFT, InquiryState.QUESTIONNAIRE_IN_PROGRESS),
            InquiryState.AI_GUIDANCE
        )
        InquiryEvent.RequestVisit -> requireState(
            current,
            setOf(InquiryState.AI_GUIDANCE, InquiryState.VISIT_REVIEW_PENDING),
            InquiryState.VISIT_SCHEDULED
        )
        InquiryEvent.CompleteVisit -> requireState(
            current,
            setOf(InquiryState.VISIT_SCHEDULED, InquiryState.COMPLETION_PENDING),
            InquiryState.RESOLVED
        )
        InquiryEvent.CancelInquiry -> when (current) {
            InquiryState.DRAFT,
            InquiryState.QUESTIONNAIRE_IN_PROGRESS -> InquiryState.CANCELLED
            else -> error("현재 상태에서는 문의를 취소할 수 없습니다: $current")
        }
    }

    private fun requireState(
        current: InquiryState?,
        allowed: Set<InquiryState>,
        next: InquiryState
    ): InquiryState {
        require(current in allowed) { "허용되지 않은 전이: $current → $next" }
        return next
    }
}
