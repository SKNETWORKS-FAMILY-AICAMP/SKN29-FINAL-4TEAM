import { describe, expect, it } from "vitest";

import {
  API_INTEGRATION_READINESS,
  BLOCKED_API_INTEGRATIONS,
  getApiIntegrationCount,
  getBlockedApiCount,
} from "../../src/features/runtime-status/model/apiIntegrationReadiness";

describe("Web Entry Gate Runtime 분류", () => {
  it("미배정 상담 배정 흐름을 포함한 상담사 Runtime 14개를 완료로 분류한다", () => {
    expect(getApiIntegrationCount("CONSULTANT", "RUNTIME_DONE")).toBe(14);
    expect(API_INTEGRATION_READINESS).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "unassigned-consultation-list",
          method: "GET",
          endpoint: "/api/v1/inquiries/unassigned-consultations",
          status: "RUNTIME_DONE",
        }),
        expect.objectContaining({
          key: "claim-consultation",
          method: "POST",
          endpoint: "/api/v1/inquiries/{id}/claim-consultation",
          status: "RUNTIME_DONE",
          contractPath: "contracts/api/paths/consultations.yaml",
        }),
      ]),
    );
  });

  it("기사 선택 Source를 Dashboard Runtime 계약에 연결한다", () => {
    expect(getBlockedApiCount("CONSULTANT")).toBe(0);
    expect(BLOCKED_API_INTEGRATIONS).toHaveLength(0);
    expect(API_INTEGRATION_READINESS).toContainEqual(expect.objectContaining({
      key: "technician-selection-source",
      method: "GET",
      endpoint: "/api/v1/consultant/dashboard",
      status: "RUNTIME_DONE",
      contractPath: "contracts/api/paths/operations.yaml",
    }));
  });

  it("모든 항목은 계약 경로와 중복되지 않은 key를 가진다", () => {
    const keys = API_INTEGRATION_READINESS.map((item) => item.key);
    expect(new Set(keys).size).toBe(keys.length);
    API_INTEGRATION_READINESS.forEach((item) => {
      expect(item.contractPath).toMatch(/^contracts\/api\/paths\/.+\.yaml$/);
    });
  });
});
