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
      await screen.findByRole("heading", { name: "Water Bridge 로그인" }),
    ).toBeInTheDocument();
  });

  it("Mock 상담사 로그인 후 원래 요청한 상담 경로로 돌아간다", async () => {
    const user = userEvent.setup();
    renderRoute("/consultant/inquiries", null);

    await user.click(
      await screen.findByRole("button", { name: "Mock 계정으로 로그인" }),
    );

    expect(
      await screen.findByRole("heading", { name: "고객 문의" }),
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
      await screen.findByRole("heading", { name: "고객 문의" }),
    ).toBeInTheDocument();
  });

  it("상담사는 전화 문의 등록 화면에 접근할 수 있다", async () => {
    renderRoute(
      "/consultant/phone-inquiries/new",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByRole("heading", { name: "전화 문의 등록" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "전화 문의 등록" }),
    ).toBeInTheDocument();
  });

  it("상담사는 CONS-02 v13 상세 경로에 직접 접근할 수 있다", async () => {
    renderRoute(
      "/consultant/inquiries/205850d3-763c-5256-9d39-82da21be0c31",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByRole("heading", { name: "문의 상세·상담 처리" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "제품 누수" }),
    ).toBeInTheDocument();
  });

  it("발표 대표 문의 DEMO-INQ-002의 완료 상세와 공식 근거를 직접 확인할 수 있다", async () => {
    const user = userEvent.setup();
    renderRoute(
      "/consultant/inquiries/bcb70ef6-01ac-5e0e-8a8d-fe5af43e8bde",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByText("문의 · DEMO-INQ-002"),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "출수량 저하" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "공식 근거·사용 상태" }));
    expect(
      screen.getByRole("heading", { name: "EvidenceCardDTO · 공식 근거" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/38쪽/)).toBeInTheDocument();
  });

  it("CONS-02 근거 부분 실패가 상세 전체를 가리지 않는다", async () => {
    renderRoute(
      "/consultant/inquiries/205850d3-763c-5256-9d39-82da21be0c31?mockFailure=evidence",
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
      "/consultant/inquiries/f72a3b18-a4f8-5f5e-8c86-199ffc1d8aa2/visit-transition",
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
      "/consultant/inquiries/a6bdf6b7-b9ba-553a-8447-f928384c1ad1/visit-transition",
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
      target: { value: "2026-07-29" },
    });
    await user.selectOptions(
      screen.getByRole("combobox", { name: /가상 방문기사/ }),
      "00000000-0000-4000-8000-000000000101",
    );
    await user.click(
      screen.getByRole("button", { name: "방문 필요 확정·요청 생성" }),
    );

    expect(
      screen.getByRole("button", { name: "일정 조율 저장" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "방문 확정" }),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "일정 조율 저장" }),
    );

    expect(
      screen.getByRole("button", { name: "방문 확정" }),
    ).toBeInTheDocument();
  });

  it.each([
    ["loading", "문의 정보를 불러오고 있습니다."],
    ["error", "문의 정보를 불러오지 못했습니다."],
    ["forbidden", "이 문의에 접근할 권한이 없습니다."],
    ["unsupported", "지원하지 않는 제품 모델입니다."],
  ])("CONS-02 %s 상태를 명확히 표시한다", async (state, message) => {
    renderRoute(
      `/consultant/inquiries/205850d3-763c-5256-9d39-82da21be0c31?mockState=${state}`,
      createUser("CONSULTANT"),
    );

    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  it("무근거 문의는 AI 실패와 근거 없음 안내를 함께 표시한다", async () => {
    const user = userEvent.setup();
    renderRoute(
      "/consultant/inquiries/dcf13b8e-e15f-5fc3-b194-0a3af2f54985",
      createUser("CONSULTANT"),
    );

    expect(await screen.findByText("FAILED")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "공식 근거·사용 상태" }));
    expect(
      screen.getByText(/연결된 공식 근거가 없습니다/),
    ).toBeInTheDocument();
  });

  it("표시용 문의 번호는 상세 URL의 리소스 ID로 사용하지 않는다", async () => {
    renderRoute(
      "/consultant/inquiries/INQ-20260704-0013",
      createUser("CONSULTANT"),
    );

    expect(
      await screen.findByText("문의를 찾을 수 없습니다."),
    ).toBeInTheDocument();
  });

  it("운영 담당자는 ADMIN-01 운영 대시보드에 접근할 수 있다", async () => {
    renderRoute("/admin", createUser("OPERATOR"));

    expect(
      await screen.findByRole("heading", { name: "운영 대시보드" }),
    ).toBeInTheDocument();
    expect(screen.getByText("ADMIN-01 · P1 MOCK")).toBeInTheDocument();
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
