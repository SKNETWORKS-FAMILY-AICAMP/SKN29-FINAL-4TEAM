import { appEnv, type MockDataset } from "../../../app/config/env";
import type { InquiryId } from "../../../entities/inquiry/inquiryIdentifiers";
import {
  CONSULTANT_QUEUE_INQUIRIES,
  COUNSELOR_INQUIRIES,
  REMOTE_PARITY_CONSULTANT_INQUIRIES,
  getConsultantAllowedActions,
} from "../model/consultantWorkspaceMock";
import type {
  CounselorAllowedAction,
  CounselorInquiry,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";

export type ConsultantWorkspaceIntegrationStatus =
  | "MOCK_ONLY"
  | "READY_FOR_WEB_INTEGRATION";

export interface ConsultantWorkspaceRepository {
  readonly dataSource: "MOCK" | "REMOTE";
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
 * 기존 동기 화면을 위한 임시 경계다.
 * Remote 모드에서는 Mock 데이터로 자동 대체하지 않고 빈 결과를 반환한다.
 * 실제 API 조회는 consultantWorkspaceDataRepository의 비동기 경계를 사용한다.
 */
export function createConsultantWorkspaceRepository(
  useMockApi: boolean,
  mockDataset: MockDataset = appEnv.mockDataset,
): ConsultantWorkspaceRepository {
  if (!useMockApi) {
    return {
      dataSource: "REMOTE",
      integrationStatus: "READY_FOR_WEB_INTEGRATION",
      findInquiry: () => undefined,
      getAllowedActions: () => [],
      listAllInquiries: () => [],
      listConsultantQueue: () => [],
    };
  }

  const mockQueue =
    mockDataset === "DESIGN_SCENARIOS"
      ? CONSULTANT_QUEUE_INQUIRIES
      : REMOTE_PARITY_CONSULTANT_INQUIRIES;

  return {
    dataSource: "MOCK",
    integrationStatus: "MOCK_ONLY",
    findInquiry: (inquiryId) =>
      mockQueue.find((item) => item.inquiryId === inquiryId) ??
      COUNSELOR_INQUIRIES.find((item) => item.inquiryId === inquiryId),
    getAllowedActions: getConsultantAllowedActions,
    listAllInquiries: () => COUNSELOR_INQUIRIES,
    listConsultantQueue: () => mockQueue,
  };
}

export const consultantWorkspaceRepository =
  createConsultantWorkspaceRepository(appEnv.useMockApi);
