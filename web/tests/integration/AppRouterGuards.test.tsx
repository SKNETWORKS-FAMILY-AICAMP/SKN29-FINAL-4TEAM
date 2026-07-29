import { fireEvent, render, screen } from "@testing-library/react";
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

  it("상담사는 CONS-02 v13 상세 경로에 직접 접근할 수 있다", async () => {
    renderRoute(
      "/consultant/inquiries/INQ-20260704-0013",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByRole("heading", { name: "문의 상세·상담 처리" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "제품 누수" }),
    ).toBeInTheDocument();
  });

  it("CONS-02 근거 부분 실패가 상세 전체를 가리지 않는다", async () => {
    renderRoute(
      "/consultant/inquiries/DEMO-INQ-EVIDENCE-ERROR",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByText("공식 근거를 불러오지 못했습니다."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "고객·제품·관리 이력" }),
    ).toBeInTheDocument();
  });

  it("방문 행동이 없는 문의의 CONS-03 직접 진입을 차단한다", async () => {
    renderRoute(
      "/consultant/inquiries/INQ-20260701-0001/visit-transition",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByText(
        "현재 상태에서는 방문 전환을 처리할 수 없습니다.",
      ),
    ).toBeInTheDocument();
  });

  it("방문 검토 상태는 요청 생성 후에만 일정 조율 행동을 연다", async () => {
    const user = userEvent.setup();
    renderRoute(
      "/consultant/inquiries/INQ-20260703-0008/visit-transition",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByRole("button", {
        name: "방문 필요 확정·요청 생성",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "일정 조율 저장" }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("고객 희망일"), {
      target: { value: "2026-07-29T10:00" },
    });
    await user.selectOptions(
      screen.getByRole("combobox", { name: /가상 방문기사/ }),
      "STAFF-TECH-01",
    );
    await user.click(
      screen.getByRole("button", { name: "방문 필요 확정·요청 생성" }),
    );

    expect(
      screen.getByRole("button", { name: "일정 조율 저장" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "방문 확정" }),
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
