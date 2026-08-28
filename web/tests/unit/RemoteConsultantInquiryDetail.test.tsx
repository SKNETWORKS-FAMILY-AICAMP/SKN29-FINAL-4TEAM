import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
      phoneMasked: "010-****-0101",
    },
    productAndCare: {
      productModel: "SYN-WP-01",
      productModelName: "합성 시연용 정수기",
      subscriptionStatus: "ACTIVE",
      managementType: "VISIT_CARE",
      recentCareDate: null,
    },
    symptomAndQuestionnaire: {
      symptomSummary: "출수량이 감소함",
      answers: [
        {
          questionCode: "SYN-Q-01",
          questionText: "필터 교체 후에도 출수량이 줄었나요?",
          answer: "필터 교체 전에도 동일",
        },
      ],
    },
    guidanceAndActions: {
      usageGuidanceStatus: "PENDING_CONSULTATION",
      usageGuidanceDisplayLabel: "상담 확인 필요",
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
  it("첫 진입에서 고객·문의·제품 확인 단계를 보여준다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(
      screen.getByRole("button", {
        name: "상담 1단계: 고객 문의 · 제품 확인",
      }),
    ).toHaveAttribute("aria-current", "step");
    expect(
      screen.getByRole("progressbar", { name: "상담 처리 진행률" }),
    ).toHaveValue(1);
    expect(screen.queryByText("GUIDED CONSULTATION")).not.toBeInTheDocument();
    expect(screen.queryByText("STEP 01")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "이전 단계" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /다음:/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent),
    ).toEqual([
      "합성고객 01",
      "고객 증상과 답변",
      "제품·관리 정보",
    ]);
    expect(
      screen.queryByRole("heading", { name: "고객에게 안내할 내용" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("상담 대기")).toBeInTheDocument();
    expect(screen.getByText("주의 문의")).toHaveClass("is-risk-caution");
    expect(screen.queryByText(/처리 우선순위/)).not.toBeInTheDocument();
    expect(screen.queryByText("합성 테스트")).not.toBeInTheDocument();
    expect(screen.queryByText("CONSULTATION_REQUIRED")).not.toBeInTheDocument();
  });

  it("상단 단계 선택으로 세 단계를 자유롭게 이동한다", async () => {
    const user = userEvent.setup();
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    const secondStep = screen.getByRole("button", {
      name: "상담 2단계: AI 상담 · 이전 상담 기록 확인",
    });
    await user.click(secondStep);

    expect(secondStep).toHaveFocus();
    expect(secondStep).toHaveAttribute("aria-current", "step");
    expect(
      screen.getByRole("heading", { name: "고객에게 안내할 내용" }),
    ).toBeVisible();
    expect(
      screen.getByRole("progressbar", { name: "상담 처리 진행률" }),
    ).toHaveValue(2);

    const thirdStep = screen.getByRole("button", {
      name: "상담 3단계: 상담 진행",
    });
    await user.click(thirdStep);

    expect(thirdStep).toHaveFocus();
    expect(thirdStep).toHaveAttribute("aria-current", "step");
    expect(
      screen.getByText("현재 진행할 상담 작업이 없습니다."),
    ).toBeVisible();

    await user.click(secondStep);
    expect(secondStep).toHaveAttribute("aria-current", "step");
  });

  it("단계를 오가도 상담 입력을 유지하고 다른 문의에서는 첫 단계로 초기화한다", async () => {
    const user = userEvent.setup();
    const action = {
      code: "UPDATE_CONSULTATION_SUMMARY",
      label: "상담 내용 저장",
      operationId: "updateConsultationSummary",
      style: "PRIMARY" as const,
      requiresConfirmation: false,
      confirmationMessage: null,
    };
    const detail = createDetail({
      status: "CONSULTATION_IN_PROGRESS",
      workflow: {
        status: "CONSULTATION_IN_PROGRESS",
        stateVersion: 5,
        allowedActions: [action],
      },
    });
    const { rerender } = render(
      <RemoteConsultantInquiryDetail
        inquiry={detail}
        onOpenVisit={() => undefined}
        onRefresh={() => undefined}
      />,
    );

    await user.click(
      screen.getByRole("button", {
        name: "상담 3단계: 상담 진행",
      }),
    );
    await user.type(screen.getByLabelText("상담 기록"), "필터 상태 확인");
    await user.click(
      screen.getByRole("button", {
        name: "상담 1단계: 고객 문의 · 제품 확인",
      }),
    );
    await user.click(
      screen.getByRole("button", {
        name: "상담 3단계: 상담 진행",
      }),
    );
    expect(screen.getByLabelText("상담 기록")).toHaveValue("필터 상태 확인");

    rerender(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({ inquiryId: "new-inquiry-id" })}
        onOpenVisit={() => undefined}
        onRefresh={() => undefined}
      />,
    );
    expect(
      screen.getByRole("button", {
        name: "상담 1단계: 고객 문의 · 제품 확인",
      }),
    ).toHaveAttribute("aria-current", "step");
  });

  it("최근 관리일 null은 관리 이력 없음으로 표시하고 날짜 요소를 만들지 않는다", () => {
    render(
      <RemoteConsultantInquiryDetail inquiry={createDetail()} />,
    );

    expect(screen.queryByText("LOW")).not.toBeInTheDocument();
    expect(screen.queryByText(/처리 우선순위/)).not.toBeInTheDocument();
    expect(screen.getByText("방문 관리")).toBeInTheDocument();
    expect(screen.getByText("관리 이력 없음")).toBeInTheDocument();
    expect(
      screen.getByText("관리 이력 없음").closest("dd")?.querySelector("time"),
    ).toBeNull();
    expect(
      screen.getByText("현재 제공된 제한 기능 정보가 없습니다."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "AI 안내가 없습니다. 고객 증상과 상담 지침을 직접 확인해 주세요.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("공식 근거는 아직 제공되지 않았습니다."),
    ).toBeInTheDocument();
  });

  it("담당 문의의 안전 Projection 최근 관리일을 날짜 이동 없이 표시한다", () => {
    render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          productAndCare: {
            productModel: "SYN-WP-01",
            productModelName: "합성 시연용 정수기",
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
            productModelName: "합성 시연용 정수기",
            subscriptionStatus: "ACTIVE",
            managementType: "VISIT_CARE",
            recentCareDate: "2026-02-31",
          },
        })}
      />,
    );

    expect(screen.getByText("최근 관리일 확인 필요")).toBeInTheDocument();
    expect(screen.queryByText("2026-02-31")).not.toBeInTheDocument();
    expect(
      screen
        .getByText("최근 관리일 확인 필요")
        .closest("dd")
        ?.querySelector("time"),
    ).toBeNull();
    expect(container.innerHTML).not.toContain("2026-02-31");
  });

  it("Backend AI 안내 상태 코드는 상담사가 이해할 수 있는 자연어로 표시한다", () => {
    render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          guidanceAndActions: {
            usageGuidanceStatus: "TOTAL_STOP",
            usageGuidanceDisplayLabel: "제품 사용 중단",
            usageGuidanceMessage: "급수 밸브를 잠그고 상담을 기다려 주세요.",
            restrictedFunctions: ["냉수 출수"],
          },
        })}
      />,
    );

    expect(screen.getByText("제품 사용 중단")).toBeInTheDocument();
    expect(screen.queryByText("TOTAL_STOP")).not.toBeInTheDocument();
    expect(
      screen.getByText("급수 밸브를 잠그고 상담을 기다려 주세요."),
    ).toBeInTheDocument();
    expect(screen.getByText("냉수 출수")).toBeInTheDocument();
    expect(screen.getByText("010-****-0101")).toBeInTheDocument();
    expect(
      screen.getAllByText("SYN-WP-01 · 합성 시연용 정수기"),
    ).toHaveLength(2);
    expect(
      screen.getByText("필터 교체 후에도 출수량이 줄었나요?"),
    ).toBeInTheDocument();
  });

  it.each([
    ["danger", "긴급 문의", "is-risk-danger"],
    ["caution", "주의 문의", "is-risk-caution"],
    ["general", "일반 문의", "is-risk-general"],
  ] as const)(
    "위험도 %s를 문의 종류와 전용 색상 class로 표시한다",
    (riskLevel, label, className) => {
      render(
        <RemoteConsultantInquiryDetail
          inquiry={createDetail({ riskLevel })}
        />,
      );

      expect(screen.getByText(label)).toHaveClass(className);
    },
  );

  it("consultation·visit null을 불필요로 해석하지 않는다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(
      screen.queryByRole("heading", { name: "방문 정보" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("이전 상담 기록·처리 이력"),
    ).not.toBeInTheDocument();
  });

  it("실행 UI가 없을 때도 Backend allowed action을 임의 버튼으로 만들지 않는다", () => {
    render(<RemoteConsultantInquiryDetail inquiry={createDetail()} />);

    expect(screen.queryByText("상담 시작")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "상담 시작" }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("상담 단계 선택")).toBeInTheDocument();
    expect(
      screen.queryByText(/allowed_actions/),
    ).not.toBeInTheDocument();
  });

  it("이전 상담 기록 팝업에서 요약과 실제 상담 내용을 함께 표시한다", async () => {
    const user = userEvent.setup();
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
            additionalCheck: "필터 체결 상태 재확인",
            customerGuidance: "정상 사용 가능 안내",
            usageGuidanceStatus: "NORMAL",
          },
        })}
      />,
    );

    expect(
      screen.queryByRole("dialog", { name: "이전 상담 기록·처리 이력" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("확정된 상담 요약")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: "상담 2단계: AI 상담 · 이전 상담 기록 확인",
      }),
    );
    await user.click(screen.getByRole("button", { name: "상세 보기" }));

    expect(
      screen.getByRole("dialog", { name: "이전 상담 기록·처리 이력" }),
    ).toBeInTheDocument();
    expect(screen.getByText("방문 없이 상담 완료")).toBeInTheDocument();
    expect(screen.queryByText("COMPLETED_NO_VISIT")).not.toBeInTheDocument();
    expect(screen.getByTestId("consultation-detail-confirmed-summary")).toHaveTextContent(
      "확정된 상담 요약",
    );
    expect(screen.getByTestId("consultation-detail-note")).toHaveTextContent(
      "고객과 필터 상태를 확인함",
    );
    expect(
      screen.getByTestId("consultation-detail-customer-guidance"),
    ).toHaveTextContent("정상 사용 가능 안내");
    expect(
      screen.getByTestId("consultation-detail-additional-check"),
    ).toHaveTextContent("필터 체결 상태 재확인");

    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("dialog", { name: "이전 상담 기록·처리 이력" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "상세 보기" })).toHaveFocus();
  });

  it("방문 필요 결과와 최신 방문 일정·기사 정보를 함께 표시한다", async () => {
    const user = userEvent.setup();
    render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          consultation: {
            consultationId: "30000000-0000-4000-8000-000000000301",
            resultCode: "VISIT_REQUIRED",
            summary: {
              aiDraftSummary: null,
              editedSummary: null,
              confirmedSummary: null,
              confirmedAt: null,
            },
            consultationNote: null,
            additionalCheck: null,
            customerGuidance: null,
            usageGuidanceStatus: "PARTIAL_STOP",
          },
          visit: {
            visitId: "40000000-0000-4000-8000-000000000401",
            inquiryId: "10000000-0000-4000-8000-000000000101",
            schedule: {
              preferredDate: "2026-08-25",
              confirmedDate: "2026-08-26",
              scheduleStatus: "CONFIRMED",
              syntheticTechnicianId:
                "50000000-0000-4000-8000-000000000501",
            },
            technician: {
              isSynthetic: true,
              technicianId: "50000000-0000-4000-8000-000000000501",
              displayName: "합성 기사 01",
              phone: "010-0000-0501",
            },
          },
        })}
      />,
    );

    await user.click(
      screen.getByRole("button", {
        name: "상담 3단계: 상담 진행",
      }),
    );

    expect(screen.getByText("방문 필요")).toBeInTheDocument();
    expect(screen.getByText("방문 정보 등록됨")).toBeInTheDocument();
    expect(screen.getByText("방문 일정 확정")).toBeInTheDocument();
    expect(screen.getByText("합성 기사 01")).toBeInTheDocument();
    expect(screen.getByText("2026. 8. 26.")).toHaveAttribute(
      "datetime",
      "2026-08-26",
    );
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

  it("처리 완료되어 가능한 작업이 없으면 실행 버튼 대신 완료 안내를 표시한다", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <RemoteConsultantInquiryDetail
        inquiry={createDetail({
          status: "RESOLVED",
          workflow: {
            status: "RESOLVED",
            stateVersion: 8,
            allowedActions: [],
          },
        })}
        onOpenVisit={() => undefined}
        onRefresh={() => undefined}
      />,
    );

    expect(screen.queryByLabelText("상담 처리 작업")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", {
        name: "상담 3단계: 상담 진행",
      }),
    );
    expect(
      screen.getByText("현재 진행할 상담 작업이 없습니다."),
    ).toBeVisible();
    expect(container.querySelector(".remote-inquiry-detail__workspace")).toBeNull();
  });
});
