import { describe, expect, it } from "vitest";

import {
  CONSULTANT_QUEUE_INQUIRIES,
  COUNSELOR_INQUIRIES,
  UNASSIGNED_CONSULTANT_INQUIRIES,
} from "../fixtures/consultantWorkspaceMock";
import { createConsultantWorkspaceRepository } from "../../src/features/consultation/repositories/consultantWorkspaceRepository";

describe("상담 업무 Repository 경계", () => {
  it("Mock 모드에서는 합성 문의 목록을 제공한다", () => {
    const repository = createConsultantWorkspaceRepository(true);

    expect(repository.integrationStatus).toBe("MOCK_ONLY");
    expect(repository.dataSource).toBe("MOCK");
    expect(repository.listAllInquiries()).toBe(COUNSELOR_INQUIRIES);
    expect(repository.listConsultantQueue()).toBe(CONSULTANT_QUEUE_INQUIRIES);
  });

  it("Remote 모드에서는 Mock으로 자동 대체하지 않는다", () => {
    const repository = createConsultantWorkspaceRepository(false);

    expect(repository.integrationStatus).toBe("READY_FOR_WEB_INTEGRATION");
    expect(repository.dataSource).toBe("REMOTE");
    expect(repository.listAllInquiries()).toEqual([]);
    expect(repository.listConsultantQueue()).toEqual([]);
    expect(repository.findInquiry(null)).toBeUndefined();
    expect(repository.getAllowedActions("CONSULTATION_REQUIRED")).toEqual([]);
  });

  it("Mock 상세 조회와 허용 행동은 Repository 경계가 담당한다", () => {
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

  it("Mock 미배정 문의도 상담 시작 후 상세에서 이어서 찾는다", () => {
    const repository = createConsultantWorkspaceRepository(true);
    const inquiry = UNASSIGNED_CONSULTANT_INQUIRIES[0];

    expect(repository.findInquiry(inquiry.inquiryId)).toMatchObject({
      inquiryId: inquiry.inquiryId,
      status: "CONSULTATION_REQUIRED",
      allowedActions: [
        expect.objectContaining({ code: "START_CONSULTATION" }),
      ],
    });
  });
});
