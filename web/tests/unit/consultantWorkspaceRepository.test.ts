import { describe, expect, it } from "vitest";

import {
  CONSULTANT_QUEUE_INQUIRIES,
  COUNSELOR_INQUIRIES,
} from "../../src/features/consultation/model/consultantWorkspaceMock";
import { createConsultantWorkspaceRepository } from "../../src/features/consultation/repositories/consultantWorkspaceRepository";

describe("상담 업무 Repository 경계", () => {
  it("Mock 모드에서 합성 목록과 상담사 큐를 한 경계로 제공한다", () => {
    const repository = createConsultantWorkspaceRepository(true);

    expect(repository.integrationStatus).toBe("MOCK_ONLY");
    expect(repository.dataSource).toBe("MOCK");
    expect(repository.listAllInquiries()).toBe(COUNSELOR_INQUIRIES);
    expect(repository.listConsultantQueue()).toBe(CONSULTANT_QUEUE_INQUIRIES);
  });

  it("실제 모드 요청 시 Endpoint를 추측하지 않고 차단 상태를 표시한다", () => {
    const repository = createConsultantWorkspaceRepository(false);

    expect(repository.integrationStatus).toBe("BACKEND_BLOCKED");
    expect(repository.dataSource).toBe("MOCK");
  });

  it("상세 조회와 Mock 허용 행동 계산을 화면 대신 Repository가 담당한다", () => {
    const repository = createConsultantWorkspaceRepository(true);
    const inquiry = COUNSELOR_INQUIRIES[0];

    expect(repository.findInquiry(inquiry.inquiryId)).toBe(inquiry);
    expect(repository.getAllowedActions("VISIT_SCHEDULING")).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ code: "UPDATE_VISIT_SCHEDULE" }),
        expect.objectContaining({ code: "CONFIRM_VISIT" }),
      ]),
    );
  });
});
