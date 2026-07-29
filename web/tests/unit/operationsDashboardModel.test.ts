import { describe, expect, it } from "vitest";

import { COUNSELOR_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";
import {
  createOperationsDashboardSummary,
  DEFAULT_OPERATIONS_FILTERS,
  filterOperationsInquiries,
  getOperationsFilterOptions,
} from "../../src/features/operations-dashboard/model/operationsDashboardModel";

describe("운영 현황 대시보드 View Model", () => {
  it("공식 합성 문의를 운영 지표와 분포로 집계한다", () => {
    const summary = createOperationsDashboardSummary(
      COUNSELOR_INQUIRIES,
      DEFAULT_OPERATIONS_FILTERS,
    );

    const total = COUNSELOR_INQUIRIES.length;

    expect(summary.inquiries).toHaveLength(total);
    expect(summary.metrics.find((metric) => metric.key === "TOTAL")?.count).toBe(total);
    expect(summary.metrics.find((metric) => metric.key === "DANGER")?.count).toBe(
      COUNSELOR_INQUIRIES.filter((inquiry) => inquiry.riskLevel === "DANGER").length,
    );
    expect(summary.symptomDistribution.reduce((sum, item) => sum + item.count, 0)).toBe(total);
    expect(summary.statusDistribution.reduce((sum, item) => sum + item.count, 0)).toBe(total);
  });

  it("기간·위험도·처리 결과 조건을 함께 적용한다", () => {
    const filtered = filterOperationsInquiries(COUNSELOR_INQUIRIES, {
      ...DEFAULT_OPERATIONS_FILTERS,
      receivedFrom: "2026-07-04",
      receivedTo: "2026-07-05",
      result: "IN_PROGRESS",
      risk: "DANGER",
    });

    expect(filtered.length).toBeGreaterThan(0);
    expect(filtered.every((inquiry) => inquiry.riskLevel === "DANGER")).toBe(true);
    expect(filtered.every((inquiry) => inquiry.status !== "RESOLVED" && inquiry.status !== "CANCELLED")).toBe(true);
    expect(filtered.every((inquiry) => inquiry.createdAt.slice(0, 10) >= "2026-07-04")).toBe(true);
    expect(filtered.every((inquiry) => inquiry.createdAt.slice(0, 10) <= "2026-07-05")).toBe(true);
  });

  it("설문 미응답·지연·근거/AI 실패를 예외 사유로 식별한다", () => {
    const summary = createOperationsDashboardSummary(
      COUNSELOR_INQUIRIES,
      DEFAULT_OPERATIONS_FILTERS,
    );
    const reasonCodes = new Set(
      summary.exceptions.flatMap((item) => item.reasons.map((reason) => reason.code)),
    );

    expect(reasonCodes).toContain("QUESTIONNAIRE_UNANSWERED");
    expect(reasonCodes).toContain("PROCESS_DELAY");
    expect(reasonCodes).toContain("EVIDENCE_SEARCH_FAILED");
    expect(reasonCodes).toContain("AI_PROCESS_FAILED");
  });

  it("빈 결과와 필터 선택지를 안전하게 만든다", () => {
    const summary = createOperationsDashboardSummary([], DEFAULT_OPERATIONS_FILTERS);
    const options = getOperationsFilterOptions(COUNSELOR_INQUIRIES);

    expect(summary.metrics.every((metric) => metric.count === 0)).toBe(true);
    expect(summary.symptomDistribution).toEqual([]);
    expect(summary.exceptions).toEqual([]);
    expect(options.productModels.length).toBeGreaterThan(0);
    expect(options.assignees).toEqual([...options.assignees].sort((left, right) => left.localeCompare(right, "ko")));
  });
});
