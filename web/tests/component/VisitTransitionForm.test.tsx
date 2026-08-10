import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
  it("방문 생성은 기사와 일정 선택 전에 완료할 수 있다", async () => {
    const user = userEvent.setup();
    const onMockSaved = vi.fn();
    render(
      <VisitTransitionForm
        availableActions={["CREATE_VISIT_REQUEST"]}
        inquiry={getVisitInquiry()}
        stateVersion={4}
        symptomSummary="누수 의심"
        onMockSaved={onMockSaved}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /방문 필요 확정.*요청 생성/ }),
    );

    expect(onMockSaved).toHaveBeenCalledWith(5, "CREATE_VISIT_REQUEST");
  });

  it("기존 임시 화면의 방문 전환 입력 항목을 모두 표시한다", () => {
    render(
      <VisitTransitionForm
        inquiry={getVisitInquiry()}
        stateVersion={4}
        symptomSummary="누수 의심"
        onMockSaved={vi.fn()}
      />,
    );

    expect(screen.getByRole("textbox", { name: /방문 사유/ })).toBeInTheDocument();
    expect(screen.getByLabelText("고객 희망일")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /가상 방문기사/ })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /점검 우선순위/ })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /기사 전달사항/ })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /안전 유의사항/ })).toBeInTheDocument();
    expect(screen.getByLabelText("가상 방문 확정일")).toBeInTheDocument();
  });

  it("필수값 오류를 표시하면서 이미 작성된 방문 사유는 유지한다", async () => {
    const user = userEvent.setup();
    render(
      <VisitTransitionForm
        inquiry={getVisitInquiry()}
        stateVersion={4}
        symptomSummary="누수 의심"
        onMockSaved={vi.fn()}
      />,
    );

    const reason = screen.getByRole("textbox", { name: /방문 사유/ });
    await user.clear(reason);
    await user.type(reason, "고객이 재방문 점검을 요청했습니다.");
    await user.click(screen.getByRole("button", { name: "일정 조율 저장" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "작성한 내용은 그대로 유지됩니다.",
    );
    expect(screen.getByText("고객 희망일을 선택해 주세요.")).toBeInTheDocument();
    expect(screen.getByText("가상 방문기사를 선택해 주세요.")).toBeInTheDocument();
    expect(reason).toHaveValue("고객이 재방문 점검을 요청했습니다.");
  });

  it("일정 조율 내용을 Mock으로 저장하고 상태 버전을 올린다", async () => {
    const user = userEvent.setup();
    const onMockSaved = vi.fn();
    render(
      <VisitTransitionForm
        inquiry={getVisitInquiry()}
        stateVersion={4}
        symptomSummary="누수 의심"
        onMockSaved={onMockSaved}
      />,
    );

    fireEvent.change(screen.getByLabelText("고객 희망일"), {
      target: { value: "2026-07-29" },
    });
    await user.selectOptions(
      screen.getByRole("combobox", { name: /가상 방문기사/ }),
      "00000000-0000-4000-8000-000000000101",
    );
    await user.click(screen.getByRole("button", { name: "일정 조율 저장" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "Mock 일정 조율 내용을 저장했습니다.",
    );
    expect(onMockSaved).toHaveBeenCalledWith(5, "SAVE_SCHEDULE");
  });

  it("방문 확정일을 입력하면 Mock 방문 확정을 완료한다", async () => {
    const user = userEvent.setup();
    const onMockSaved = vi.fn();
    render(
      <VisitTransitionForm
        inquiry={getVisitInquiry()}
        stateVersion={4}
        symptomSummary="누수 의심"
        onMockSaved={onMockSaved}
      />,
    );

    fireEvent.change(screen.getByLabelText("고객 희망일"), {
      target: { value: "2026-07-29" },
    });
    await user.selectOptions(
      screen.getByRole("combobox", { name: /가상 방문기사/ }),
      "00000000-0000-4000-8000-000000000102",
    );
    fireEvent.change(screen.getByLabelText("가상 방문 확정일"), {
      target: { value: "2026-07-30" },
    });
    await user.click(screen.getByRole("button", { name: "방문 확정" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "Mock 방문 일정이 확정되었습니다.",
    );
    expect(onMockSaved).toHaveBeenCalledWith(5, "CONFIRM_VISIT");
  });

  it("allowed_actions에 없는 방문 확정 버튼은 표시하지 않는다", () => {
    render(
      <VisitTransitionForm
        availableActions={["SAVE_SCHEDULE"]}
        inquiry={getVisitInquiry()}
        stateVersion={4}
        symptomSummary="누수 의심"
        onMockSaved={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "일정 조율 저장" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "방문 확정" }),
    ).not.toBeInTheDocument();
  });
});
