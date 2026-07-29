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
});
