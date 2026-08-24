import type { CounselorInquiry } from "./consultantWorkspaceTypes";

export { getConsultantAllowedActions } from "./consultantWorkspaceMockActions";

// Production builds resolve this module. Mock fixture data is available only to
// development and test builds through the Vite alias in vite.config.ts.
export const COUNSELOR_INQUIRIES: readonly CounselorInquiry[] = Object.freeze(
  [],
);

export const CONSULTANT_QUEUE_INQUIRIES: readonly CounselorInquiry[] =
  COUNSELOR_INQUIRIES;

export const REMOTE_PARITY_CONSULTANT_INQUIRIES: readonly CounselorInquiry[] =
  COUNSELOR_INQUIRIES;

export const UNASSIGNED_CONSULTANT_INQUIRIES: readonly CounselorInquiry[] =
  COUNSELOR_INQUIRIES;

export const REMOTE_PARITY_UNASSIGNED_CONSULTANT_INQUIRIES: readonly CounselorInquiry[] =
  COUNSELOR_INQUIRIES;
