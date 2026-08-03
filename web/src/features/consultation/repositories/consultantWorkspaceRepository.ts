import { appEnv } from "../../../app/config/env";
import type { InquiryId } from "../../../entities/inquiry/inquiryIdentifiers";
import {
  CONSULTANT_QUEUE_INQUIRIES,
  COUNSELOR_INQUIRIES,
  getConsultantAllowedActions,
} from "../model/consultantWorkspaceMock";
import type {
  CounselorAllowedAction,
  CounselorInquiry,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";

export type ConsultantWorkspaceIntegrationStatus =
  | "MOCK_ONLY"
  | "BACKEND_BLOCKED";

export interface ConsultantWorkspaceRepository {
  readonly dataSource: "MOCK";
  readonly integrationStatus: ConsultantWorkspaceIntegrationStatus;
  findInquiry(inquiryId: InquiryId | null): CounselorInquiry | undefined;
  getAllowedActions(
    status: CounselorStatus,
    feedbackResolved?: boolean,
  ): readonly CounselorAllowedAction[];
  listAllInquiries(): readonly CounselorInquiry[];
  listConsultantQueue(): readonly CounselorInquiry[];
}

/**
 * 실제 상담사 조회·저장 Endpoint가 확정될 때까지 화면의 데이터 접근을 한곳에 모은다.
 * VITE_USE_MOCK_API=false여도 Endpoint를 추측하지 않으며, Mock 미리보기와
 * BACKEND_BLOCKED 상태를 명시적으로 유지한다.
 */
export function createConsultantWorkspaceRepository(
  useMockApi: boolean,
): ConsultantWorkspaceRepository {
  return {
    dataSource: "MOCK",
    integrationStatus: useMockApi ? "MOCK_ONLY" : "BACKEND_BLOCKED",
    findInquiry: (inquiryId) =>
      COUNSELOR_INQUIRIES.find((item) => item.inquiryId === inquiryId),
    getAllowedActions: getConsultantAllowedActions,
    listAllInquiries: () => COUNSELOR_INQUIRIES,
    listConsultantQueue: () => CONSULTANT_QUEUE_INQUIRIES,
  };
}

export const consultantWorkspaceRepository =
  createConsultantWorkspaceRepository(appEnv.useMockApi);
