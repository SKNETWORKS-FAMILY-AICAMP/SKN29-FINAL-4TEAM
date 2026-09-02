import type {
  CounselorActionCode,
  CounselorAllowedAction,
  CounselorStatus,
} from "./consultantWorkspaceTypes";

export const ACTIONS = {
  CANCEL_INQUIRY: {
    code: "CANCEL_INQUIRY",
    label: "문의 삭제",
    operationId: "cancelInquiry",
    style: "DESTRUCTIVE",
    requiresConfirmation: true,
    confirmationMessage:
      "문의를 삭제하시겠습니까? 문의는 취소 상태로 전환되며 처리 이력은 보관됩니다.",
  },
  START_CONSULTATION: {
    code: "START_CONSULTATION",
    label: "상담 시작",
    operationId: "startConsultation",
    style: "PRIMARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  UPDATE_CONSULTATION_SUMMARY: {
    code: "UPDATE_CONSULTATION_SUMMARY",
    label: "상담 내용 수정",
    operationId: "updateConsultationSummary",
    style: "SECONDARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  CONFIRM_CONSULTATION_SUMMARY: {
    code: "CONFIRM_CONSULTATION_SUMMARY",
    label: "상담 내용 확정",
    operationId: "confirmConsultationSummary",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "상담을 확정하시겠습니까?",
  },
  CONSULTATION_COMPLETED: {
    code: "CONSULTATION_COMPLETED",
    label: "상담 처리 완료",
    operationId: "completeConsultation",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "상담 처리를 완료하고 고객 확인 단계로 전환하시겠습니까?",
  },
  VISIT_REVIEW_REQUIRED: {
    code: "VISIT_REVIEW_REQUIRED",
    label: "방문 필요 여부 검토",
    operationId: "requestVisitReview",
    style: "SECONDARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  VISIT_NEEDED: {
    code: "VISIT_NEEDED",
    label: "방문 필요 확정",
    operationId: "createVisitRequest",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "방문 요청을 생성하시겠습니까?",
  },
  VISIT_NOT_NEEDED: {
    code: "VISIT_NOT_NEEDED",
    label: "방문 불필요 확정",
    operationId: "markVisitNotNeeded",
    style: "SECONDARY",
    requiresConfirmation: true,
    confirmationMessage: "방문 없이 상담 처리 결과 확인 단계로 전환하시겠습니까?",
  },
  UPDATE_VISIT_SCHEDULE: {
    code: "UPDATE_VISIT_SCHEDULE",
    label: "방문 일정 조율",
    operationId: "updateVisitSchedule",
    style: "SECONDARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  CONFIRM_VISIT: {
    code: "CONFIRM_VISIT",
    label: "방문 일정 확정",
    operationId: "confirmVisit",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "담당 기사와 방문 일정을 확정하시겠습니까?",
  },
  RESUME_CONSULTATION: {
    code: "RESUME_CONSULTATION",
    label: "상담 대기열로 복귀",
    operationId: "resumeConsultation",
    style: "PRIMARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  FINALIZE_INQUIRY: {
    code: "FINALIZE_INQUIRY",
    label: "문의 최종 완료",
    operationId: "finalizeInquiry",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "고객 해결 확인을 검토하고 문의를 최종 완료하시겠습니까?",
  },
} as const satisfies Record<CounselorActionCode, CounselorAllowedAction>;

export function getConsultantAllowedActions(
  status: CounselorStatus,
  feedbackResolved = false,
): readonly CounselorAllowedAction[] {
  const byStatus: Partial<
    Record<CounselorStatus, readonly CounselorAllowedAction[]>
  > = {
    DRAFT: [ACTIONS.CANCEL_INQUIRY],
    QUESTIONNAIRE_IN_PROGRESS: [ACTIONS.CANCEL_INQUIRY],
    CONSULTATION_REQUIRED: [
      ACTIONS.START_CONSULTATION,
      ACTIONS.CANCEL_INQUIRY,
    ],
    CONSULTATION_IN_PROGRESS: [
      ACTIONS.UPDATE_CONSULTATION_SUMMARY,
      ACTIONS.CONFIRM_CONSULTATION_SUMMARY,
      ACTIONS.CONSULTATION_COMPLETED,
      ACTIONS.VISIT_REVIEW_REQUIRED,
      ACTIONS.CANCEL_INQUIRY,
    ],
    VISIT_REVIEW_PENDING: [ACTIONS.VISIT_NEEDED, ACTIONS.VISIT_NOT_NEEDED],
    VISIT_SCHEDULING: [ACTIONS.UPDATE_VISIT_SCHEDULE, ACTIONS.CONFIRM_VISIT],
    REVISIT_REQUIRED: [ACTIONS.UPDATE_VISIT_SCHEDULE],
    REOPENED: [ACTIONS.RESUME_CONSULTATION],
    COMPLETION_PENDING: feedbackResolved ? [ACTIONS.FINALIZE_INQUIRY] : [],
  };

  return byStatus[status] ?? [];
}
