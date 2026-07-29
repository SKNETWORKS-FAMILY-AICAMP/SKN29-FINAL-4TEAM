import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ConsultationActionPanel from "../../src/features/consultation/components/ConsultationActionPanel";
import { COUNSELOR_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";

function getInquiry(code: string) {
  const inquiry = COUNSELOR_INQUIRIES.find(
    (item) => item.inquiryCode === code,
  );
  if (!inquiry) throw new Error(`테스트 문의를 찾을 수 없습니다: ${code}`);
  return inquiry;
}

describe("ConsultationActionPanel", () => {
  it("Backend Mock allowed_actions에 포함된 상담 진행 행동만 표시한다", () => {
    render(
      <ConsultationActionPanel
        inquiry={getInquiry("INQ-20260704-0013")}
        onOpenVisit={vi.fn()}
      />,
    );

    const panel = screen.getByRole("complementary", { name: "상담 처리 작업" });
    expect(within(panel).getByRole("button", { name: "상담 요약 수정" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "상담 요약 확정" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "방문 필요 여부 검토" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "상담 처리 완료" })).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: "상담 시작" })).not.toBeInTheDocument();
  });

  it("완료 필수값 오류를 각 입력 항목에 연결한다", async () => {
    const user = userEvent.setup();
    render(
      <ConsultationActionPanel
        inquiry={getInquiry("INQ-20260704-0013")}
        onOpenVisit={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "상담 처리 완료" }));

    expect(screen.getByText("상담 기록을 입력해 주세요.")).toBeInTheDocument();
    expect(screen.getByText("고객에게 안내한 내용을 입력해 주세요.")).toBeInTheDocument();
    expect(screen.getByText("상담 결과를 입력해 주세요.")).toBeInTheDocument();
    expect(screen.getByText("방문 필요 여부를 선택해 주세요.")).toBeInTheDocument();
  });

  it("409 충돌 후 작성 내용을 유지하고 최신 stateVersion을 반영한다", async () => {
    const user = userEvent.setup();
    render(
      <ConsultationActionPanel
        inquiry={getInquiry("INQ-20260704-0013")}
        onOpenVisit={vi.fn()}
      />,
    );

    const note = screen.getByRole("textbox", { name: /상담 기록/ });
    await user.type(note, "고객 사용 상태를 추가로 확인했습니다.");
    await user.selectOptions(
      screen.getByRole("combobox", { name: /Mock 응답 테스트/ }),
      "CONFLICT",
    );
    await user.click(screen.getByRole("button", { name: "상담 요약 수정" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "작성 내용은 유지했으며 최신 상태를 반영했습니다.",
    );
    expect(note).toHaveValue("고객 사용 상태를 추가로 확인했습니다.");
    expect(alert).toHaveTextContent(
      `최신 stateVersion ${getInquiry("INQ-20260704-0013").stateVersion + 1} 반영`,
    );
  });

  it("멱등 키 재사용 409를 최신 상태 Snapshot으로 오인하지 않는다", async () => {
    const user = userEvent.setup();
    const inquiry = getInquiry("INQ-20260704-0013");
    render(
      <ConsultationActionPanel inquiry={inquiry} onOpenVisit={vi.fn()} />,
    );

    const note = screen.getByRole("textbox", { name: /상담 기록/ });
    await user.type(note, "재시도 전 작성한 상담 기록");
    await user.selectOptions(
      screen.getByRole("combobox", { name: /Mock 응답 테스트/ }),
      "DUPLICATE_EVENT",
    );
    await user.click(screen.getByRole("button", { name: "상담 요약 수정" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("같은 Idempotency-Key에 다른 요청 내용이 사용되었습니다.");
    expect(alert).toHaveTextContent("최신 상태 Snapshot 미적용");
    expect(note).toHaveValue("재시도 전 작성한 상담 기록");
    expect(
      screen.getByText(
        `${inquiry.inquiryCode} · stateVersion ${inquiry.stateVersion}`,
      ),
    ).toBeInTheDocument();
  });

  it("상담사 행동이 허용되지 않은 문진 상태에서는 처리 버튼을 숨긴다", () => {
    render(
      <ConsultationActionPanel
        inquiry={getInquiry("INQ-20260701-0001")}
        onOpenVisit={vi.fn()}
      />,
    );

    expect(
      screen.getByText("현재 서버 Mock이 상담사에게 허용한 처리 행동이 없습니다."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("저장 성공 후 최신 상세 Snapshot 갱신 완료를 표시한다", async () => {
    const user = userEvent.setup();
    render(
      <ConsultationActionPanel
        inquiry={getInquiry("INQ-20260704-0013")}
        onOpenVisit={vi.fn()}
      />,
    );

    await user.type(
      screen.getByRole("textbox", { name: /상담 기록/ }),
      "고객 상태 확인",
    );
    await user.click(screen.getByRole("button", { name: "상담 요약 수정" }));

    expect(
      await screen.findByText("최신 상세 Snapshot 갱신 완료"),
    ).toBeInTheDocument();
  });
});
