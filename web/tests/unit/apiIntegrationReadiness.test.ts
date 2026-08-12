import { describe, expect, it } from "vitest";

import {
  API_INTEGRATION_READINESS,
  BLOCKED_API_INTEGRATIONS,
  getApiIntegrationCount,
  getBlockedApiCount,
} from "../../src/features/runtime-status/model/apiIntegrationReadiness";

describe("Web Entry Gate Runtime 분류", () => {
  it("상담사 P0 11개 Endpoint를 실제 Runtime 완료로 분류한다", () => {
    expect(getApiIntegrationCount("CONSULTANT", "RUNTIME_DONE")).toBe(11);
  });

  it("기사 선택 Source만 Backend blocker로 남긴다", () => {
    expect(getBlockedApiCount("CONSULTANT")).toBe(1);
    expect(BLOCKED_API_INTEGRATIONS[0]).toMatchObject({
      key: "technician-selection-source",
      status: "BLOCKED_BY_BACKEND",
    });
  });

  it("모든 항목은 계약 경로와 중복되지 않은 key를 가진다", () => {
    const keys = API_INTEGRATION_READINESS.map((item) => item.key);
    expect(new Set(keys).size).toBe(keys.length);
    API_INTEGRATION_READINESS.forEach((item) => {
      expect(item.contractPath).toMatch(/^contracts\/api\/paths\/.+\.yaml$/);
    });
  });
});
