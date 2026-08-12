import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";

const CONSULTANT_USER = {
  id: "STAFF-PHONE-TEST",
  displayName: "전화 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

function renderPage() {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={["/consultant/phone-inquiries/new"]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("PhoneInquiryCreatePage", () => {
  it("전화 문의 내용을 직접 입력해 최근 기록에 추가한다", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByRole("tab", { name: "전화 문의 등록" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await user.type(screen.getByLabelText("고객명 *"), "김전화");
    await user.type(screen.getByLabelText("연락처 *"), "010-1234-5678");
    await user.selectOptions(
      screen.getByLabelText("문의 유형 *"),
      "누수·안전 문의",
    );
    await user.type(
      screen.getByLabelText("문의 내용 *"),
      "정수기 아래에서 물이 새어 안전 확인을 요청했습니다.",
    );
    await user.click(
      screen.getByLabelText("고객에게 개인정보 수집·이용 안내를 완료했습니다. *"),
    );
    await user.click(screen.getByRole("button", { name: "전화 문의 저장" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "김전화 고객의 전화 문의가 임시 저장되었습니다.",
    );
    const recentRecords = screen.getByRole("complementary", {
      name: "최근 전화 문의 접수 내역",
    });
    expect(
      within(recentRecords).getByRole("heading", { name: "김전화" }),
    ).toBeInTheDocument();
    expect(within(recentRecords).getByText("010-1234-5678")).toBeInTheDocument();
    expect(within(recentRecords).getByText("누수·안전 문의")).toBeInTheDocument();
  });
});
