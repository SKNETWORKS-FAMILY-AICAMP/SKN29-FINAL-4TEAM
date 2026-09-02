import type { ConsultantInquiryDetailViewModel } from "./consultantWorkspaceRemoteMapper";
import type { CounselorActionCode } from "./consultantWorkspaceTypes";

const REMOTE_CONSULTATION_ACTION_CODES = new Set<CounselorActionCode>([
  "CANCEL_INQUIRY",
  "START_CONSULTATION",
  "UPDATE_CONSULTATION_SUMMARY",
  "CONFIRM_CONSULTATION_SUMMARY",
  "CONSULTATION_COMPLETED",
  "VISIT_REVIEW_REQUIRED",
  "VISIT_NEEDED",
  "VISIT_NOT_NEEDED",
  "UPDATE_VISIT_SCHEDULE",
  "CONFIRM_VISIT",
  "RESUME_CONSULTATION",
  "FINALIZE_INQUIRY",
]);

export function isRemoteConsultationActionCode(
  value: string,
): value is CounselorActionCode {
  return REMOTE_CONSULTATION_ACTION_CODES.has(value as CounselorActionCode);
}

export function hasRemoteConsultationAction(
  inquiry: ConsultantInquiryDetailViewModel,
): boolean {
  return inquiry.workflow.allowedActions.some((action) =>
    isRemoteConsultationActionCode(action.code),
  );
}
