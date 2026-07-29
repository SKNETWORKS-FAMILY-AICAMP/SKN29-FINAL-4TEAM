import { describe, expect, it } from "vitest";

import {
  CONSULTANT_QUEUE_INQUIRIES,
  COUNSELOR_INQUIRIES,
} from "../../src/features/consultation/model/consultantWorkspaceMock";
import {
  filterCounselorInquiries,
  getCounselorRoutingDecision,
  getCounselorQueuePage,
  normalizeCounselorRisk,
  normalizeCounselorStatus,
} from "../../src/features/consultation/model/consultantWorkspaceModel";
import type { CounselorFilters } from "../../src/features/consultation/model/consultantWorkspaceTypes";

const DEFAULT_FILTERS: CounselorFilters = {
  assignee: "ALL",
  consultation: "ALL",
  page: 1,
  priority: "ALL",
  query: "",
  receivedFrom: "",
  receivedTo: "",
  risk: "ALL",
  sort: "UPDATED_DESC",
  status: "ALL",
};

describe("상담 큐 View Model", () => {
  it("담당자·우선순위·접수 기간 조건을 함께 적용한다", () => {
    const result = filterCounselorInquiries(COUNSELOR_INQUIRIES, {
      ...DEFAULT_FILTERS,
      assignee: "MINE",
      priority: "URGENT",
      receivedFrom: "2026-07-04",
      receivedTo: "2026-07-04",
    });

    expect(result.map((item) => item.inquiryCode)).toEqual([
      "INQ-20260704-0013",
    ]);
  });

  it("페이지 범위를 넘으면 마지막 페이지로 보정한다", () => {
    const result = getCounselorQueuePage(COUNSELOR_INQUIRIES, {
      ...DEFAULT_FILTERS,
      page: 99,
    });
    const expectedLastPage = Math.ceil(COUNSELOR_INQUIRIES.length / 3);
    const expectedLastPageItems =
      COUNSELOR_INQUIRIES.length - (expectedLastPage - 1) * 3;

    expect(result.currentPage).toBe(expectedLastPage);
    expect(result.totalItems).toBe(COUNSELOR_INQUIRIES.length);
    expect(result.items).toHaveLength(expectedLastPageItems);
  });

  it("공식 fixture의 일반 문의는 AI가 방문기사에게 자동 인계한다", () => {
    const inquiry = COUNSELOR_INQUIRIES.find(
      (item) => item.scenarioId === "SYN-JAC104-022",
    );

    expect(inquiry).toMatchObject({
      usageStatus: "PENDING_CONSULTATION",
      requiresConsultation: false,
      aiStatus: "FAILED",
      evidence: [],
      routingTarget: "FIELD_TECHNICIAN",
      status: "VISIT_SCHEDULING",
      assignedCounselor: "방문기사 자동 인계",
    });
  });

  it("일반은 방문기사, 주의·긴급은 상담사로 최초 라우팅한다", () => {
    expect(getCounselorRoutingDecision("GENERAL").target).toBe(
      "FIELD_TECHNICIAN",
    );
    expect(getCounselorRoutingDecision("CAUTION").target).toBe("CONSULTANT");
    expect(getCounselorRoutingDecision("DANGER").target).toBe("CONSULTANT");
    expect(
      CONSULTANT_QUEUE_INQUIRIES.every(
        (item) => item.routingTarget === "CONSULTANT",
      ),
    ).toBe(true);
  });

  it("알 수 없는 상태·위험도 코드는 미확인 값으로 안전하게 변환한다", () => {
    expect(normalizeCounselorStatus("NEW_SERVER_STATUS")).toBe("UNKNOWN");
    expect(normalizeCounselorRisk("new-risk")).toBe("UNKNOWN");
    expect(normalizeCounselorRisk(null)).toBe("UNKNOWN");
  });
});
