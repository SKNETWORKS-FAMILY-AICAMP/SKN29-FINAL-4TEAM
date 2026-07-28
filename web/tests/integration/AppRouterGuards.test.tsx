import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
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

function renderRoute(
  path: string,
  initialUser: AuthenticatedUser | null,
) {
  return render(
    <AuthProvider initialUser={initialUser}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("App Router Guard", () => {
  it("인증되지 않은 사용자는 요청 경로 대신 로그인 화면으로 이동한다", async () => {
    renderRoute("/consultant/inquiries", null);

    expect(
      await screen.findByRole("heading", { name: "워터케어 ONE 로그인" }),
    ).toBeInTheDocument();
  });

  it("Mock 상담사 로그인 후 원래 요청한 상담 경로로 돌아간다", async () => {
    const user = userEvent.setup();
    renderRoute("/consultant/inquiries", null);

    await user.click(
      await screen.findByRole("button", { name: "Mock 계정으로 로그인" }),
    );

    expect(
      await screen.findByRole("heading", { name: "상담·문의 큐" }),
    ).toBeInTheDocument();
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
      await screen.findByRole("heading", { name: "상담·문의 큐" }),
    ).toBeInTheDocument();
  });

  it("운영 담당자는 ADMIN-01 Placeholder에 접근할 수 있다", async () => {
    renderRoute("/admin", createUser("OPERATOR"));

    expect(
      await screen.findByRole("heading", { name: "운영 대시보드" }),
    ).toBeInTheDocument();
    expect(screen.getByText("ADMIN-01 · PLACEHOLDER")).toBeInTheDocument();
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
