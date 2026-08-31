import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ConsultantCompletionNotice from "../../src/features/consultation/components/ConsultantCompletionNotice";
import {
  CONSULTANT_COMPLETED_LIST_PATH,
  createConsultantCompletionState,
  readConsultantCompletionNotice,
} from "../../src/features/consultation/model/consultantCompletionNavigation";

describe("상담사 완료 목록 이동 안내 상태", () => {
  it("완료 목록 경로를 사용하되 서버의 실제 상태와 opaque ID를 그대로 보존한다", () => {
    const inquiryId = "case:한글/non-uuid?part=7";
    const state = createConsultantCompletionState(
      "PHONE_REGISTERED", inquiryId, "CONSULTATION_REQUIRED",
    );

    expect(CONSULTANT_COMPLETED_LIST_PATH)
      .toBe("/consultant/inquiries?bucket=COMPLETED");
    expect(readConsultantCompletionNotice(state)).toEqual({
      source: "PHONE_REGISTERED",
      inquiryId,
      status: "CONSULTATION_REQUIRED",
    });
  });

  it.each([
    null,
    undefined,
    "not-navigation-state",
    {},
    { consultantCompletion: null },
    { consultantCompletion: { source: "UNKNOWN", inquiryId: "case-1", status: "RESOLVED" } },
    { consultantCompletion: { source: "PHONE_REGISTERED", inquiryId: "", status: "RESOLVED" } },
    { consultantCompletion: { source: "PHONE_REGISTERED", inquiryId: "  ", status: "RESOLVED" } },
    { consultantCompletion: { source: "PHONE_REGISTERED", inquiryId: 123, status: "RESOLVED" } },
    { consultantCompletion: { source: "PHONE_REGISTERED", inquiryId: "case-1" } },
  ])("필수 정보가 없는 이동 상태는 안내로 렌더링하지 않는다: %j", (navigationState) => {
    expect(readConsultantCompletionNotice(navigationState)).toBeNull();
    const { container } = render(
      <ConsultantCompletionNotice
        navigationState={navigationState}
        onOpenInquiry={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("알 수 없는 서버 상태를 임의의 완료 상태로 바꾸지 않는다", () => {
    const navigationState = {
      consultantCompletion: {
        source: "PHONE_REGISTERED",
        inquiryId: "opaque-case-2",
        status: "FUTURE_SERVER_STATUS",
      },
    };
    expect(readConsultantCompletionNotice(navigationState)?.status).toBe("UNKNOWN");
    render(
      <ConsultantCompletionNotice
        navigationState={navigationState}
        onOpenInquiry={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByRole("region", { name: "문의 처리 결과" }))
      .toHaveTextContent("현재 문의 상태는 ‘미확인’입니다.");
  });
});

describe("상담사 문의 처리 결과 안내", () => {
  it.each([
    ["CONSULTATION_CONFIRMED", "CONSULTATION_IN_PROGRESS", "상담 내용이 확정되었습니다.", "상담 진행 중"],
    ["CONSULTATION_CONFIRMED", "COMPLETION_PENDING", "상담 내용이 확정되었습니다.", "최종 완료 대기"],
    ["PHONE_REGISTERED", "CONSULTATION_REQUIRED", "전화 문의가 등록되었습니다.", "상담 대기"],
  ] as const)("%s 후 %s는 실제 완료 전임을 안내한다", (source, status, message, statusLabel) => {
    render(
      <ConsultantCompletionNotice
        navigationState={createConsultantCompletionState(source, "case:opaque-3", status)}
        onOpenInquiry={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    const notice = screen.getByRole("region", { name: "문의 처리 결과" });
    expect(within(notice).getByRole("status")).toHaveTextContent(message);
    expect(notice).toHaveTextContent(`현재 문의 상태는 ‘${statusLabel}’입니다.`);
    expect(notice).toHaveTextContent("실제 완료 처리 전에는 완료 목록에 표시되지 않습니다.");
  });

  it("서버가 RESOLVED를 반환한 경우에는 미완료 안내를 표시하지 않는다", () => {
    render(
      <ConsultantCompletionNotice
        navigationState={createConsultantCompletionState("CONSULTATION_CONFIRMED", "resolved:case-4", "RESOLVED")}
        onOpenInquiry={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    expect(screen.getByRole("status"))
      .toHaveTextContent("상담 내용이 확정되었습니다.");
    expect(screen.queryByText(/실제 완료 처리 전/)).not.toBeInTheDocument();
  });

  it("해당 문의 확인은 opaque ID를 전달하고 닫기는 부모에게 안내 해제를 요청한다", async () => {
    const user = userEvent.setup();
    const onOpenInquiry = vi.fn();
    const onDismiss = vi.fn();
    const inquiryId = "opaque:한글/ticket?key=5";
    render(
      <ConsultantCompletionNotice
        navigationState={createConsultantCompletionState("PHONE_REGISTERED", inquiryId, "CONSULTATION_REQUIRED")}
        onOpenInquiry={onOpenInquiry}
        onDismiss={onDismiss}
      />,
    );

    await user.click(screen.getByRole("button", { name: "해당 문의 확인" }));
    expect(onOpenInquiry).toHaveBeenCalledExactlyOnceWith(inquiryId);
    expect(onDismiss).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "문의 처리 결과 안내 닫기" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
