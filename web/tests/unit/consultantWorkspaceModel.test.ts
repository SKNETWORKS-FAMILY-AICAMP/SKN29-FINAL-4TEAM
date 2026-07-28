import { describe, expect, it } from "vitest";

import { COUNSELOR_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";
import {
  filterCounselorInquiries,
  getCounselorQueuePage,
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
      receivedFrom: "2026-07-22",
      receivedTo: "2026-07-22",
    });

    expect(result.map((item) => item.id)).toEqual([
      "DEMO-INQ-006",
      "DEMO-INQ-004",
    ]);
  });

  it("페이지 범위를 넘으면 마지막 페이지로 보정한다", () => {
    const result = getCounselorQueuePage(COUNSELOR_INQUIRIES, {
      ...DEFAULT_FILTERS,
      page: 99,
    });

    expect(result.currentPage).toBe(3);
    expect(result.totalItems).toBe(7);
    expect(result.items).toHaveLength(1);
  });
});
