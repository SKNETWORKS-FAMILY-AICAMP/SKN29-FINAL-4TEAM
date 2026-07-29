import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";
import { CONSULTANT_QUEUE_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";

const CONSULTANT_USER = {
  id: "STAFF-CONS-TEST",
  displayName: "테스트 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

function renderPage(path = "/consultant/inquiries") {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("ConsultantDashboardPage", () => {
  it("문의 목록에서 상담 진행 문의를 선택하면 상담 Form을 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("searchbox", { name: "문의 검색" }),
      "INQ-20260704-0013",
    );
    await user.click(screen.getByRole("button", { name: /INQ-20260704-0013/ }));

    expect(screen.getByRole("heading", { name: "제품 누수" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /상담 기록/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "상담 처리 완료" })).toBeInTheDocument();
  });

  it("위험도 필터는 공식 fixture의 위험 문의만 큐에 남긴다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByText("추가 필터"));
    await user.selectOptions(screen.getByRole("combobox", { name: "위험도" }), "DANGER");

    const queue = screen.getByRole("complementary", { name: "상담 문의 목록" });
    const dangerCount = CONSULTANT_QUEUE_INQUIRIES.filter(
      (item) => item.riskLevel === "DANGER",
    ).length;
    const firstPageCount = Math.min(dangerCount, 3);

    expect(queue.querySelectorAll(".v6-queue-item")).toHaveLength(firstPageCount);
    expect(
      screen.getByText(`총 ${dangerCount}건 · 1/${Math.ceil(dangerCount / 3)}페이지`),
    ).toBeInTheDocument();
    expect(within(queue).getAllByLabelText("위험도: 긴급")).toHaveLength(
      firstPageCount,
    );
  });

  it("페이지와 담당자 조건을 URL Query에서 복원한다", async () => {
    const user = userEvent.setup();
    renderPage("/consultant/inquiries?assignee=UNASSIGNED&page=1");
    const unassignedCount = CONSULTANT_QUEUE_INQUIRIES.filter(
      (item) => item.assignedCounselor === "미배정",
    ).length;
    const totalPages = Math.ceil(unassignedCount / 3);

    await user.click(screen.getByText("추가 필터"));
    expect(screen.getByRole("combobox", { name: "담당자" })).toHaveValue(
      "UNASSIGNED",
    );
    expect(
      screen.getByRole("heading", { name: "IoT 기능 지원 문의" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(`총 ${unassignedCount}건 · 1/${totalPages}페이지`),
    ).toBeInTheDocument();
  });

  it("일반 문의는 AI가 방문기사에게 자동 인계하여 상담사 큐에 노출하지 않는다", () => {
    renderPage();

    const queue = screen.getByRole("complementary", { name: "상담 문의 목록" });
    expect(within(queue).queryByLabelText("위험도: 일반")).not.toBeInTheDocument();
    expect(
      CONSULTANT_QUEUE_INQUIRIES.every(
        (item) => item.riskLevel === "CAUTION" || item.riskLevel === "DANGER",
      ),
    ).toBe(true);
  });

  it.each([
    ["loading", "상담 문의 목록을 불러오고 있습니다."],
    ["error", "상담 문의 목록을 불러오지 못했습니다."],
    ["forbidden", "상담 문의 목록을 볼 권한이 없습니다."],
    ["empty", "아직 접수된 문의가 없습니다."],
  ])("목록 %s 상태를 다른 상태와 구분한다", async (state, message) => {
    renderPage(`/consultant/inquiries?mockState=${state}`);

    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  it("검색 결과가 없으면 초기 빈 목록과 다른 안내와 초기화 행동을 제공한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("searchbox", { name: "문의 검색" }),
      "존재하지 않는 문의",
    );

    expect(screen.getByText("조건에 맞는 문의가 없습니다.")).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "조건 초기화" }).length,
    ).toBeGreaterThan(0);
  });
});
