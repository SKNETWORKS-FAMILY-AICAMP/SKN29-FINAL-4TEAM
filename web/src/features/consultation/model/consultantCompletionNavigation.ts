import { ROUTE_PATHS } from "../../../app/router/routePaths";
import type { InquiryId } from "../../../entities/inquiry/inquiryIdentifiers";
import { normalizeCounselorStatus } from "./consultantWorkspaceModel";
import type { CounselorStatus } from "./consultantWorkspaceTypes";

export const CONSULTANT_COMPLETED_LIST_PATH = `${ROUTE_PATHS.consultantInquiryList}?bucket=COMPLETED`;

type CompletionNoticeSource = "CONSULTATION_CONFIRMED" | "PHONE_REGISTERED";

export interface ConsultantCompletionNotice {
  source: CompletionNoticeSource;
  inquiryId: InquiryId;
  status: CounselorStatus;
}

// This is navigation feedback only. The list and counters still use the API's
// real status; confirming a summary or registering a call never implies RESOLVED.
export function createConsultantCompletionState(
  source: CompletionNoticeSource,
  inquiryId: string,
  status: CounselorStatus,
) {
  return { consultantCompletion: { source, inquiryId, status } };
}

export function readConsultantCompletionNotice(
  state: unknown,
): ConsultantCompletionNotice | null {
  if (!state || typeof state !== "object" || !("consultantCompletion" in state)) return null;
  const notice = state.consultantCompletion;
  if (!notice || typeof notice !== "object") return null;
  if (!("source" in notice) ||
    (notice.source !== "CONSULTATION_CONFIRMED" && notice.source !== "PHONE_REGISTERED")) return null;
  if (!("inquiryId" in notice) || !("status" in notice)) return null;
  if (typeof notice.inquiryId !== "string" || !notice.inquiryId.trim()) return null;
  const inquiryId = notice.inquiryId as InquiryId;
  return {
    source: notice.source,
    inquiryId,
    status: normalizeCounselorStatus(notice.status),
  };
}
