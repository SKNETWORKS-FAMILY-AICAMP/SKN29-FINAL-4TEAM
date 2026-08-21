export type ApiIntegrationGroup = "CONSULTANT" | "OPERATIONS";

export type ApiIntegrationStatus =
  | "RUNTIME_DONE"
  | "READY_FOR_WEB_INTEGRATION"
  | "BLOCKED_BY_BACKEND"
  | "CONTRACT_ONLY"
  | "MOCK_ONLY"
  | "NOT_P0";

export interface ApiIntegrationReadinessItem {
  key: string;
  group: ApiIntegrationGroup;
  label: string;
  method?: "GET" | "POST" | "PATCH";
  endpoint?: string;
  status: ApiIntegrationStatus;
  contractPath: string;
  blocker?: string;
}

const P0_RUNTIME_ENDPOINTS = [
  ["consultant-list", "상담사 문의 목록", "GET", "/api/v1/inquiries", "contracts/api/paths/inquiries.yaml"],
  ["consultant-detail", "상담사 문의 상세", "GET", "/api/v1/inquiries/{id}", "contracts/api/paths/inquiries.yaml"],
  ["consultation-start", "상담 시작", "POST", "/api/v1/inquiries/{id}/start-consultation", "contracts/api/paths/consultations.yaml"],
  ["consultation-save", "상담 기록 저장", "PATCH", "/api/v1/inquiries/{id}/consultation-summary", "contracts/api/paths/consultations.yaml"],
  ["consultation-confirm", "상담 요약 확정", "POST", "/api/v1/inquiries/{id}/consultation-summary/confirm", "contracts/api/paths/consultations.yaml"],
  ["consultation-complete", "상담 완료", "POST", "/api/v1/inquiries/{id}/complete-consultation", "contracts/api/paths/consultations.yaml"],
  ["visit-review", "방문 필요 검토", "POST", "/api/v1/inquiries/{id}/visit-review", "contracts/api/paths/visits.yaml"],
  ["visit-create", "방문 생성", "POST", "/api/v1/inquiries/{id}/visits", "contracts/api/paths/visits.yaml"],
  ["visit-not-needed", "방문 불필요 확정", "POST", "/api/v1/inquiries/{id}/visit-not-needed", "contracts/api/paths/visits.yaml"],
  ["visit-schedule", "기사·방문 일정 저장", "PATCH", "/api/v1/visits/{visit_id}/schedule", "contracts/api/paths/visits.yaml"],
  ["visit-confirm", "방문 확정", "POST", "/api/v1/visits/{visit_id}/confirm", "contracts/api/paths/visits.yaml"],
] as const;

export const API_INTEGRATION_READINESS: readonly ApiIntegrationReadinessItem[] = [
  ...P0_RUNTIME_ENDPOINTS.map(([key, label, method, endpoint, contractPath]) => ({
    key,
    group: "CONSULTANT" as const,
    label,
    method,
    endpoint,
    status: "RUNTIME_DONE" as const,
    contractPath,
  })),
  {
    key: "technician-selection-source",
    group: "CONSULTANT",
    label: "합성 기사 선택 Source",
    method: "GET",
    endpoint: "/api/v1/consultant/dashboard",
    status: "RUNTIME_DONE",
    contractPath: "contracts/api/paths/operations.yaml",
  },
  {
    key: "consultant-ai-evidence",
    group: "CONSULTANT",
    label: "상담사 AI·Evidence 공개 DTO",
    status: "CONTRACT_ONLY",
    contractPath: "contracts/api/paths/inquiries.yaml",
    blocker: "DEC-008 공개 DTO와 Backend 조립 Runtime이 필요합니다.",
  },
  {
    key: "operations-summary",
    group: "OPERATIONS",
    label: "운영 대시보드 집계",
    status: "MOCK_ONLY",
    contractPath: "contracts/api/paths/operations.yaml",
    blocker: "상담사 P0 범위가 아니며 운영 Runtime이 아직 없습니다.",
  },
];

export const BLOCKED_API_INTEGRATIONS = API_INTEGRATION_READINESS.filter(
  (item) => item.status === "BLOCKED_BY_BACKEND",
);

export function getApiIntegrationCount(group: ApiIntegrationGroup, status?: ApiIntegrationStatus): number {
  return API_INTEGRATION_READINESS.filter(
    (item) => item.group === group && (!status || item.status === status),
  ).length;
}

export function getBlockedApiCount(group: ApiIntegrationGroup): number {
  return getApiIntegrationCount(group, "BLOCKED_BY_BACKEND");
}
