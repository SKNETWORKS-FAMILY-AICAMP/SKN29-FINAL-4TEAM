import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";
import { COUNSELOR_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";

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

function getTotalMetric() {
  const label = screen.getByText("조회 문의", { selector: ".operations-metric > span" });
  return label.closest("article");
}

describe("ADMIN-01 운영 현황 대시보드", () => {
  it("운영 지표·분포·예외 목록을 공식 합성 문의로 표시한다", async () => {
    renderDashboard();

    expect(await screen.findByRole("heading", { name: "운영 대시보드" })).toBeInTheDocument();
    expect(within(getTotalMetric()!).getByText(String(COUNSELOR_INQUIRIES.length))).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "주요 증상 유형" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "운영 예외 건" })).toBeInTheDocument();
  });

  it("위험도 필터를 URL 상태로 적용하고 초기화한다", async () => {
    const user = userEvent.setup();
    renderDashboard();
    const riskSelect = await screen.findByRole("combobox", { name: "위험도" });
    const resetButton = screen.getByRole("button", { name: "조건 초기화" });

    expect(resetButton).toBeDisabled();
    await user.selectOptions(riskSelect, "DANGER");

    expect(riskSelect).toHaveValue("DANGER");
    expect(within(getTotalMetric()!).getByText(
      String(COUNSELOR_INQUIRIES.filter((item) => item.riskLevel === "DANGER").length),
    )).toBeInTheDocument();
    expect(resetButton).toBeEnabled();

    await user.click(resetButton);
    expect(riskSelect).toHaveValue("ALL");
    expect(within(getTotalMetric()!).getByText(String(COUNSELOR_INQUIRIES.length))).toBeInTheDocument();
  });

  it("loading·empty·error 상태를 각각 안내한다", async () => {
    const loading = renderDashboard("/admin?mockState=loading");
    expect(await screen.findByText("운영 현황을 집계하고 있습니다.")).toBeInTheDocument();
    loading.unmount();

    const empty = renderDashboard("/admin?mockState=empty");
    expect(await screen.findAllByText("현재 조회 조건에 맞는 문의가 없습니다.")).not.toHaveLength(0);
    empty.unmount();

    renderDashboard("/admin?mockState=error");
    expect(await screen.findByText("운영 현황을 불러오지 못했습니다.")).toBeInTheDocument();
  });

  it("목록 없이 운영 지표만 보는 인포그래픽 전용 화면을 제공한다", async () => {
    renderDashboard("/admin/insights");

    expect(
      await screen.findByRole("heading", { name: "운영 인포그래픽" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "주요 증상 유형" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "문의 처리 상태" })).toBeInTheDocument();
    expect(screen.queryByText("조건별 문의 현황")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /인포그래픽/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});
