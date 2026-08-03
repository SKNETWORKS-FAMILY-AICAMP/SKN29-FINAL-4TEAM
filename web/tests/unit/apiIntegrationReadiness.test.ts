import { describe, expect, it } from "vitest";

import {
  BLOCKED_API_INTEGRATIONS,
  getBlockedApiCount,
} from "../../src/features/runtime-status/model/apiIntegrationReadiness";

describe("실제 API 전환 준비 목록", () => {
  it("상담사 5개와 운영자 1개의 교체 지점을 관리한다", () => {
    expect(getBlockedApiCount("CONSULTANT")).toBe(5);
    expect(getBlockedApiCount("OPERATIONS")).toBe(1);
  });

  it("모든 교체 지점은 계약 파일과 현재 Mock 위치를 함께 알려준다", () => {
    expect(BLOCKED_API_INTEGRATIONS).toHaveLength(6);

    BLOCKED_API_INTEGRATIONS.forEach((item) => {
      expect(item.contractPath).toMatch(/^contracts\/api\/paths\/.+\.yaml$/);
      expect(item.mockSource).toMatch(/\.ts$/);
    });
  });

  it("같은 교체 지점이 중복 등록되지 않는다", () => {
    const keys = BLOCKED_API_INTEGRATIONS.map((item) => item.key);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
