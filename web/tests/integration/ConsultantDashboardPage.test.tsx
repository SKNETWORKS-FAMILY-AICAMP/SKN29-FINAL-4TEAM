import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import ConsultantDashboardPage from "../../src/pages/consultant/ConsultantDashboardPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <ConsultantDashboardPage />
    </MemoryRouter>,
  );
}

describe("ConsultantDashboardPage", () => {
  it("문의 목록에서 상담 진행 문의를 선택하면 상담 Form을 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /냉수 온도 이상/ }));

    expect(screen.getByRole("heading", { name: "냉수 온도 이상" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /상담 기록/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "상담 처리 완료" })).toBeInTheDocument();
  });

  it("위험도 필터는 위험 문의 두 건만 큐에 남긴다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByRole("combobox", { name: "위험도" }), "DANGER");

    const queue = screen.getByRole("complementary", { name: "상담 문의 목록" });
    expect(within(queue).getAllByRole("button")).toHaveLength(2);
    expect(within(queue).getByText("온수 모듈 이상")).toBeInTheDocument();
    expect(within(queue).getByText("제품 누수")).toBeInTheDocument();
  });
});

