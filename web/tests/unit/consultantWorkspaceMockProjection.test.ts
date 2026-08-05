import { describe, expect, it } from "vitest";

import { getMockBackendInquiryProjection } from "../../src/features/consultation/api/consultantWorkspaceMockProjection";

describe("상담 업무 Mock Backend Projection", () => {
  it("업무 상태와 담당자 값을 화면 계산 없이 명시된 Snapshot으로 제공한다", () => {
    expect(getMockBackendInquiryProjection("SYN-JAC104-022")).toEqual(
      expect.objectContaining({
        status: "VISIT_SCHEDULING",
        riskLevel: "GENERAL",
        priority: "NORMAL",
        routingTarget: "FIELD_TECHNICIAN",
        waitingMinutes: 60,
        assignedCounselor: "방문기사 자동 인계",
        allowedActionCodes: [],
      }),
    );
  });

  it("허용 행동도 상태로 재계산하지 않고 Snapshot 값을 제공한다", () => {
    expect(
      getMockBackendInquiryProjection("SYN-JAC104-013").allowedActionCodes,
    ).toEqual([
      "UPDATE_CONSULTATION_SUMMARY",
      "CONFIRM_CONSULTATION_SUMMARY",
      "CONSULTATION_COMPLETED",
      "VISIT_REVIEW_REQUIRED",
    ]);
  });

  it("정의되지 않은 시나리오는 조용히 추측하지 않고 오류로 차단한다", () => {
    expect(() =>
      getMockBackendInquiryProjection("SYN-JAC104-UNKNOWN"),
    ).toThrow("Mock Backend Projection이 없습니다");
  });
});
