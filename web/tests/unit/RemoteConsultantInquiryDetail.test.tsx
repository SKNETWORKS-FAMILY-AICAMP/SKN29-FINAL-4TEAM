import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RemoteConsultantInquiryDetail from "../../src/features/consultation/components/RemoteConsultantInquiryDetail";
import type { ConsultantInquiryDetailViewModel } from "../../src/features/consultation/model/consultantWorkspaceRemoteMapper";

function createDetail(
  overrides: Partial<ConsultantInquiryDetailViewModel> = {},
): ConsultantInquiryDetailViewModel {
  return {
    inquiryId: "10000000-0000-4000-8000-000000000101",
    inquiryCode: "SYN-INQ-0101",
    status: "CONSULTATION_REQUIRED",
    stateVersion: 4,
    riskLevel: "caution",
    priority: "LOW",
    receivedAt: "2026-08-04T04:10:00Z",
    updatedAt: "2026-08-04T04:20:00Z",
    customer: {
      isSynthetic: true,
      displayName: "합성고객 01",
      phone: "010-0000-0101",
    },
    productAndCare: {
      productModel: "SYN-WP-01",
      subscriptionStatus: "ACTIVE",
      managementType: "VISIT_CARE",
      recentCareDate: null,
    },
    symptomAndQuestionnaire: {
      symptomSummary: "출수량이 감소함",
      answers: [{ questionCode: "SYN-Q-01", answer: "필터 교체 전에도 동일" }],
    },
    guidanceAndActions: {
      usageGuidanceStatus: "PENDING_CONSULTATION",
      usageGuidanceMessage: null,
      restrictedFunctions: [],
    },
    consultation: null,
    visit: null,
    stateHistory: [],
    workflow: {
      status: "CONSULTATION_REQUIRED",
      stateVersion: 4,
      allowedActions: [
        {
          code: "START_CONSULTATION",
          label: "상담 시작",
          operationId: "startConsultation",
          style: "PRIMARY",
          requiresConfirmation: false,
          confirmationMessage: null,
        },
      ],
    },
    sectionErrors: [],
    ...overrides,
  };
}

describe("Remote 상담사 문의 상세", () => {
  it("LOW·관리 유형·최근 관리일 null을 계약대로 표시한다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(screen.getByText("LOW")).toBeInTheDocument();
    expect(screen.getByText("방문 관리")).toBeInTheDocument();
    expect(screen.getByText("관리 이력 없음")).toBeInTheDocument();
    expect(screen.getByText("제한 정보 미제공")).toBeInTheDocument();
  });

  it("consultation·visit null을 불필요로 해석하지 않는다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(screen.getByText("상담 기록이 아직 제공되지 않았습니다.")).toBeInTheDocument();
    expect(screen.getByText("방문 기록이 아직 제공되지 않았습니다.")).toBeInTheDocument();
  });

  it("쓰기 Runtime 전에는 allowed action을 버튼으로 활성화하지 않는다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(screen.getByText("상담 시작")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(
      screen.getByText("상담·방문 저장 API가 준비될 때까지 실행 버튼은 제공하지 않습니다."),
    ).toBeInTheDocument();
  });

  it("Section 오류는 다른 상세 정보와 함께 부분 오류로 표시한다", () => {
    render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          productAndCare: null,
          sectionErrors: [
            {
              section: "product_and_care",
              code: "PRODUCT_SECTION_FAILED",
              message: "제품 정보를 불러오지 못했습니다.",
            },
          ],
        })}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "제품 정보를 불러오지 못했습니다.",
    );
    expect(screen.getByText("합성고객 01")).toBeInTheDocument();
  });
});
