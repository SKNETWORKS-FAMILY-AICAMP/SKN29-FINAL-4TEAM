export type ApiIntegrationGroup = "CONSULTANT" | "OPERATIONS";

export type ApiIntegrationReadinessItem = {
  key: string;
  group: ApiIntegrationGroup;
  label: string;
  contractPath: string;
  mockSource: string;
};

/**
 * 실제 API가 확정되면 Mock에서 교체해야 하는 화면 연결 지점입니다.
 * Endpoint를 추측해서 넣지 않고, 팀이 합의해야 할 계약 파일만 가리킵니다.
 */
export const BLOCKED_API_INTEGRATIONS: readonly ApiIntegrationReadinessItem[] = [
  {
    key: "consultant-inquiry-list",
    group: "CONSULTANT",
    label: "상담사 문의 목록",
    contractPath: "contracts/api/paths/inquiries.yaml",
    mockSource: "features/consultation/model/consultantWorkspaceMock.ts",
  },
  {
    key: "consultant-inquiry-detail",
    group: "CONSULTANT",
    label: "상담사 문의 상세",
    contractPath: "contracts/api/paths/inquiries.yaml",
    mockSource: "features/consultation/model/consultantWorkspaceMock.ts",
  },
  {
    key: "consultation-save",
    group: "CONSULTANT",
    label: "상담 기록 저장·완료",
    contractPath: "contracts/api/paths/consultations.yaml",
    mockSource: "features/consultation/api/consultationMockApi.ts",
  },
  {
    key: "technician-assignment",
    group: "CONSULTANT",
    label: "방문기사 배정",
    contractPath: "contracts/api/paths/visits.yaml",
    mockSource: "features/visit-transition/model/visitTransitionMock.ts",
  },
  {
    key: "visit-schedule",
    group: "CONSULTANT",
    label: "방문 일정 저장·확정",
    contractPath: "contracts/api/paths/visits.yaml",
    mockSource: "features/visit-transition/model/visitTransitionMock.ts",
  },
  {
    key: "operations-summary",
    group: "OPERATIONS",
    label: "운영 대시보드 집계",
    contractPath: "contracts/api/paths/operations.yaml",
    mockSource: "features/consultation/model/consultantWorkspaceMock.ts",
  },
];

export function getBlockedApiCount(group: ApiIntegrationGroup): number {
  return BLOCKED_API_INTEGRATIONS.filter((item) => item.group === group).length;
}
