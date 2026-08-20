import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";

const CONSULTANT_USER = {
  id: "STAFF-CONS-NOTICE-TEST",
  displayName: "테스트 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

function renderPage(path = "/consultant/notices") {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("ConsultantNoticePage", () => {
  it("상담사 메뉴에서 공지사항 페이지를 열고 전체 공지를 보여준다", async () => {
    const user = userEvent.setup();
    renderPage("/consultant/dashboard");

    await user.click(screen.getByRole("tab", { name: "공지사항" }));

    const panel = await screen.findByRole("tabpanel", { name: "공지사항" });
    expect(
      within(panel).getByText("상담 업무에 필요한 안내와 일정을 확인해 주세요."),
    ).toBeVisible();
    expect(within(panel).getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByRole("tab", { name: "공지사항" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getAllByRole("tab").at(-1)).toHaveAccessibleName("공지사항");
  });

  it("분류와 검색어로 필요한 공지만 찾을 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();

    const panel = await screen.findByRole("tabpanel", { name: "공지사항" });
    await user.click(within(panel).getByRole("button", { name: "시스템" }));
    expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
    expect(within(panel).getByText("상담 시스템 정기 점검 안내")).toBeVisible();

    await user.click(within(panel).getByRole("button", { name: "전체" }));
    await user.type(within(panel).getByRole("searchbox"), "건강검진");
    expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
    expect(within(panel).getByText("임직원 건강검진 신청 안내")).toBeVisible();
  });
});
