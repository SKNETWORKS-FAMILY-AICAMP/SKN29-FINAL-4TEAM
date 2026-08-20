import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";

function renderDashboard(path = "/admin") {
  return render(
    <AuthProvider
      initialUser={{
        id: "STAFF-OP-TEST",
        displayName: "운영 테스트",
        roleCode: "OPERATOR",
        isActive: true,
      }}
    >
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("ADMIN-01 운영 현황 대시보드", () => {
  it("Backend 집계 API가 없을 때 연동 대기 상태만 표시한다", async () => {
    renderDashboard();

    expect(await screen.findByRole("heading", { name: "운영 대시보드" })).toBeInTheDocument();
    expect(screen.getByText("운영 집계 API 연동을 기다리고 있습니다.")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("주요 증상 유형")).not.toBeInTheDocument();
    expect(screen.queryByText("운영 예외 건")).not.toBeInTheDocument();
  });

  it("인포그래픽도 로컬 집계를 숨기고 연동 대기 상태를 표시한다", async () => {
    renderDashboard("/admin/insights");

    expect(
      await screen.findByRole("heading", { name: "운영 인포그래픽" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("운영 인포그래픽 API 연동을 기다리고 있습니다."),
    ).toBeInTheDocument();
    expect(screen.queryByText("주요 증상 유형")).not.toBeInTheDocument();
    expect(screen.queryByText("문의 처리 상태")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /인포그래픽/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});
