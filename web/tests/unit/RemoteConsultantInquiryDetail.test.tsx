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
  it("한 화면에서 상담에 필요한 상세 영역을 순서대로 보여준다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(
      screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent),
    ).toEqual([
      "고객 정보",
      "제품·관리 정보",
      "증상·문진",
      "사용 안내",
      "상담·방문 정보",
      "현재 가능한 작업",
      "문의 정보",
    ]);
  });

  it("최근 관리일 null은 관리 이력 없음으로 표시하고 날짜 요소를 만들지 않는다", () => {
    const { container } = render(
      <RemoteConsultantInquiryDetail inquiry={createDetail()} />,
    );

    expect(screen.getByText("LOW")).toBeInTheDocument();
    expect(screen.getByText("방문 관리")).toBeInTheDocument();
    expect(screen.getByText("관리 이력 없음")).toBeInTheDocument();
    expect(container.querySelector("time")).not.toBeInTheDocument();
    expect(screen.getByText("제한 정보 미제공")).toBeInTheDocument();
    expect(screen.getByText("AI 안내 미제공 / 상담 검토 필요")).toBeInTheDocument();
    expect(screen.getByText("공개 근거 미제공 / 상담 검토 필요")).toBeInTheDocument();
  });

  it("담당 문의의 안전 Projection 최근 관리일을 날짜 이동 없이 표시한다", () => {
    render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          productAndCare: {
            productModel: "SYN-WP-01",
            subscriptionStatus: "ACTIVE",
            managementType: "VISIT_CARE",
            recentCareDate: "2026-08-01",
          },
        })}
      />,
    );

    expect(screen.getByText("2026. 8. 1.")).toHaveAttribute(
      "datetime",
      "2026-08-01",
    );
  });

  it("잘못된 최근 관리일은 원문과 날짜 속성을 숨기고 확인 필요로 표시한다", () => {
    const { container } = render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          productAndCare: {
            productModel: "SYN-WP-01",
            subscriptionStatus: "ACTIVE",
            managementType: "VISIT_CARE",
            recentCareDate: "2026-02-31",
          },
        })}
      />,
    );

    expect(screen.getByText("최근 관리일 확인 필요")).toBeInTheDocument();
    expect(screen.queryByText("2026-02-31")).not.toBeInTheDocument();
    expect(container.querySelector("time")).not.toBeInTheDocument();
    expect(container.innerHTML).not.toContain("2026-02-31");
  });

  it("Backend AI 안내 상태 코드는 상담사가 이해할 수 있는 자연어로 표시한다", () => {
    render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          guidanceAndActions: {
            usageGuidanceStatus: "TOTAL_STOP",
            usageGuidanceMessage: "급수 밸브를 잠그고 상담을 기다려 주세요.",
            restrictedFunctions: ["냉수 출수"],
          },
        })}
      />,
    );

    expect(screen.getByText("제품 전체 사용 중지")).toBeInTheDocument();
    expect(screen.queryByText("TOTAL_STOP")).not.toBeInTheDocument();
    expect(
      screen.getByText("급수 밸브를 잠그고 상담을 기다려 주세요."),
    ).toBeInTheDocument();
    expect(screen.getByText("냉수 출수")).toBeInTheDocument();
  });

  it("consultation·visit null을 불필요로 해석하지 않는다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(screen.getByText("상담 기록이 아직 제공되지 않았습니다.")).toBeInTheDocument();
    expect(screen.getByText("방문 기록이 아직 제공되지 않았습니다.")).toBeInTheDocument();
  });

  it("실행 UI가 없을 때도 Backend allowed action을 임의 버튼으로 만들지 않는다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(screen.getByText("상담 시작")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(
      screen.getByText("Backend가 반환한 allowed_actions만 실행 버튼으로 제공합니다."),
    ).toBeInTheDocument();
  });

  it("재조회된 상담 기록과 확정 요약을 표시한다", () => {
    render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          consultation: {
            consultationId: "30000000-0000-4000-8000-000000000301",
            resultCode: "COMPLETED_NO_VISIT",
            summary: {
              aiDraftSummary: "AI 초안",
              editedSummary: "상담사 수정 요약",
              confirmedSummary: "확정된 상담 요약",
              confirmedAt: "2026-08-13T10:30:00+09:00",
            },
            consultationNote: "고객과 필터 상태를 확인함",
            additionalCheck: null,
            customerGuidance: "정상 사용 가능 안내",
            usageGuidanceStatus: "NORMAL",
          },
        })}
      />,
    );

    expect(screen.getByText("COMPLETED_NO_VISIT")).toBeInTheDocument();
    expect(screen.getByTestId("consultation-detail-confirmed-summary")).toHaveTextContent(
      "확정된 상담 요약",
    );
    expect(screen.getByTestId("consultation-detail-note")).toHaveTextContent(
      "고객과 필터 상태를 확인함",
    );
    expect(
      screen.getByTestId("consultation-detail-customer-guidance"),
    ).toHaveTextContent("정상 사용 가능 안내");
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
