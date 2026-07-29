import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";

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

    await user.selectOptions(screen.getByRole("combobox", { name: "위험도" }), "DANGER");

    const queue = screen.getByRole("complementary", { name: "상담 문의 목록" });
    expect(queue.querySelectorAll(".v6-queue-item")).toHaveLength(3);
    expect(screen.getByText("총 6건 · 1/2페이지")).toBeInTheDocument();
    expect(within(queue).getAllByText("온수 모듈 이상")).toHaveLength(2);
  });

  it("페이지와 담당자 조건을 URL Query에서 복원한다", () => {
    renderPage("/consultant/inquiries?assignee=UNASSIGNED&page=1");

    expect(screen.getByRole("combobox", { name: "담당자" })).toHaveValue(
      "UNASSIGNED",
    );
    expect(
      screen.getByRole("heading", { name: "IoT 기능 지원 문의" }),
    ).toBeInTheDocument();
    expect(screen.getByText("총 15건 · 1/5페이지")).toBeInTheDocument();
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
