import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import type {
  AppRole,
  AuthenticatedUser,
} from "../../src/app/providers/authContext";
import { AppRoutes } from "../../src/app/router/AppRouter";

function createUser(roleCode: AppRole): AuthenticatedUser {
  return {
    id: `TEST-${roleCode}`,
    displayName: `테스트 ${roleCode}`,
    roleCode,
    isActive: true,
  };
}

function RouterLocationProbe() {
  const location = useLocation();
  return (
    <span data-testid="router-location" hidden>
      {location.pathname}
      {location.search}
    </span>
  );
}

function renderRoute(
  path: string,
  initialUser: AuthenticatedUser | null,
) {
  return render(
    <AuthProvider initialUser={initialUser}>
      <MemoryRouter initialEntries={[path]}>
        <RouterLocationProbe />
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("App Router Guard", () => {
  it("인증되지 않은 사용자는 요청 경로 대신 로그인 화면으로 이동한다", async () => {
    renderRoute("/consultant/inquiries", null);

    expect(
      await screen.findByRole("heading", { name: "Water Bridge 로그인" }),
    ).toBeInTheDocument();
  });

  it("Mock 상담사 로그인 후 원래 요청한 상담 경로로 돌아간다", async () => {
    const user = userEvent.setup();
    renderRoute("/consultant/inquiries?bucket=NEW&q=누수", null);

    await user.click(
      await screen.findByRole("button", { name: "Mock 계정으로 로그인" }),
    );

    expect(
      await screen.findByRole("heading", { name: "고객 문의" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("router-location")).toHaveTextContent(
      "/consultant/inquiries?bucket=NEW&q=누수",
    );
  });

  it("운영 담당자가 상담사 경로에 접근하면 403 화면으로 이동한다", async () => {
    renderRoute("/consultant/inquiries", createUser("OPERATOR"));

    expect(
      await screen.findByText("이 역할로 접근할 수 없는 화면입니다."),
    ).toBeInTheDocument();
  });

  it("상담사는 상담 큐에 접근할 수 있다", async () => {
    renderRoute("/consultant/inquiries", createUser("CONSULTANT"));

    expect(
      await screen.findByRole("heading", { name: "고객 문의" }),
    ).toBeInTheDocument();
  });

  it("상담사는 별도 업무 대시보드에 접근할 수 있다", async () => {
    renderRoute("/consultant/dashboard", createUser("CONSULTANT"));

    expect(
      await screen.findByRole("heading", {
        name: "테스트 CONSULTANT님 반갑습니다!",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "업무 대시보드" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("상담사는 전화 문의 등록 화면에 접근할 수 있다", async () => {
    renderRoute(
      "/consultant/phone-inquiries/new",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByRole("tabpanel", { name: "전화 문의 등록" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "전화 문의 등록" }),
    ).toBeInTheDocument();
  });

  it("기존 문의 상세 URL은 문의 목록으로 이동하고 같은 문의 드로어를 연다", async () => {
    const user = userEvent.setup();
    const inquiryId = "205850d3-763c-5256-9d39-82da21be0c31";

    renderRoute(
      `/consultant/inquiries/${inquiryId}`,
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByRole("heading", { name: "고객 문의" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("router-location")).toHaveTextContent(
      `/consultant/inquiries?inquiryId=${inquiryId}`,
    );
    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(screen.getByText("INQ-20260704-0013")).toBeInTheDocument();

    await user.click(
      screen.getAllByRole("button", { name: "문의 상세 닫기" })[0],
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("router-location")).toHaveTextContent(
      /^\/consultant\/inquiries$/,
    );
  });

  it("방문 행동이 없는 문의의 CONS-03 직접 진입을 차단한다", async () => {
    renderRoute(
      "/consultant/inquiries/f72a3b18-a4f8-5f5e-8c86-199ffc1d8aa2/visit-transition",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByText(
        "현재 상태에서는 방문 전환을 처리할 수 없습니다.",
      ),
    ).toBeInTheDocument();
  });

  it("방문 검토 상태에서도 기사 선택·배정 API가 없으면 비활성화한다", async () => {
    renderRoute(
      "/consultant/inquiries/a6bdf6b7-b9ba-553a-8447-f928384c1ad1/visit-transition",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByRole("heading", {
        name: "기사 선택·배정 API 미지원",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "기사 선택·배정 비활성화" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("combobox", { name: /방문기사/ }),
    ).not.toBeInTheDocument();
    ["방문 필요 확정·요청 생성", "일정 조율 저장", "방문 확정"].forEach(
      (name) =>
        expect(screen.queryByRole("button", { name })).not.toBeInTheDocument(),
    );
  });

  it("표시용 문의 번호가 들어간 기존 URL은 문의를 임의 선택하지 않는다", async () => {
    renderRoute(
      "/consultant/inquiries/INQ-20260704-0013",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByRole("heading", { name: "고객 문의" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("운영 담당자는 ADMIN-01 운영 대시보드에 접근할 수 있다", async () => {
    renderRoute("/admin", createUser("OPERATOR"));

    expect(
      await screen.findByRole("heading", { name: "운영 대시보드" }),
    ).toBeInTheDocument();
    expect(screen.getByText("ADMIN-01 · API PENDING")).toBeInTheDocument();
  });

  it("상담사가 운영 경로에 접근하면 403 화면으로 이동한다", async () => {
    renderRoute("/admin", createUser("CONSULTANT"));

    expect(
      await screen.findByText("이 역할로 접근할 수 없는 화면입니다."),
    ).toBeInTheDocument();
  });

  it("등록되지 않은 경로는 404 화면으로 이동한다", async () => {
    renderRoute("/missing-page", createUser("CONSULTANT"));

    expect(
      await screen.findByText("페이지를 찾을 수 없습니다."),
    ).toBeInTheDocument();
  });
});
