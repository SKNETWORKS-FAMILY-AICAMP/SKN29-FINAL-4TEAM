import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import VisitTransitionForm from "../../src/features/visit-transition/components/VisitTransitionForm";
import { COUNSELOR_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";

function getVisitInquiry() {
  const inquiry = COUNSELOR_INQUIRIES.find(
    (item) => item.inquiryCode === "INQ-20260703-0008",
  );
  if (!inquiry) throw new Error("방문 전환 테스트 문의를 찾을 수 없습니다.");
  return inquiry;
}

describe("VisitTransitionForm", () => {
  it("기사 선택·배정 API가 없으면 입력과 로컬 성공 처리를 제공하지 않는다", () => {
    render(
      <VisitTransitionForm
        inquiry={getVisitInquiry()}
        stateVersion={4}
        symptomSummary="누수 의심"
      />,
    );

    expect(
      screen.getByRole("heading", { name: "기사 선택·배정 API 미지원" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: /가상 방문기사/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("고객 희망일")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("가상 방문 확정일")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "기사 선택·배정 비활성화" }),
    ).toBeDisabled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("로컬 저장 없이 문의 맥락과 상태 버전만 표시한다", () => {
    const inquiry = getVisitInquiry();
    render(
      <VisitTransitionForm
        inquiry={inquiry}
        stateVersion={4}
        symptomSummary="누수 의심"
      />,
    );

    expect(screen.getByText(inquiry.inquiryCode)).toBeVisible();
    expect(screen.getByText("누수 의심")).toBeVisible();
    expect(screen.getByText("stateVersion 4")).toBeVisible();
    expect(
      screen.getByText("고정 기사, 로컬 저장, 성공 메시지로 대체하지 않습니다."),
    ).toBeVisible();
  });
});
