import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../src/app/config/env", () => ({
  appEnv: {
    apiBaseUrl: "/api/v1",
    enableDesignMockFallback: false,
    mockAuthenticated: false,
    mockDataset: "REMOTE_PARITY",
    mockRole: "CONSULTANT",
    useMockApi: false,
  },
}));

vi.mock("../../src/features/auth/api/authApi", () => ({
  DEMO_USER_CODES: {
    CUSTOMER: "DEMO-CUSTOMER-001",
    CONSULTANT: "DEMO-CONSULTANT-001",
    TECHNICIAN: "DEMO-TECHNICIAN-001",
    OPERATOR: "DEMO-OPERATOR-001",
  },
  getCurrentUser: vi.fn(),
  loginWithDemoCode: vi.fn(),
  loginWithPassword: vi.fn(),
  refreshAuthSession: vi.fn(),
  revokeRefreshToken: vi.fn(),
}));

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { useAuth } from "../../src/app/providers/authContext";
import {
  getCurrentUser,
  loginWithDemoCode,
  loginWithPassword,
} from "../../src/features/auth/api/authApi";
import {
  authSessionStore,
  type AuthSession,
} from "../../src/features/auth/model/authSession";

const LOGIN_USER = {
  id: "00000000-0000-4000-8000-000000000102",
  displayName: "로그인 응답 상담사",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

const CURRENT_USER = {
  ...LOGIN_USER,
  displayName: "/me 응답 상담사",
};

const LOGIN_SESSION: AuthSession = {
  accessToken: "remote-access-token",
  refreshToken: "remote-refresh-token",
  accessExpiresIn: 3600,
  refreshExpiresIn: 604800,
  user: LOGIN_USER,
};

function RemoteAuthHarness() {
  const { isLoading, signInAs, signInWithPassword, user } = useAuth();

  return (
    <>
      <p>{isLoading ? "인증 확인 중" : (user?.displayName ?? "로그인 필요")}</p>
      <button type="button" onClick={() => void signInAs("CONSULTANT")}>
        데모 로그인
      </button>
      <button
        type="button"
        onClick={() => void signInWithPassword("consultant", "safe-password")}
      >
        비밀번호 로그인
      </button>
    </>
  );
}

describe("AuthProvider 원격 사용자 동기화", () => {
  beforeEach(() => {
    authSessionStore.clear();
    vi.mocked(loginWithDemoCode).mockResolvedValue(LOGIN_SESSION);
    vi.mocked(loginWithPassword).mockResolvedValue(LOGIN_SESSION);
    vi.mocked(getCurrentUser).mockResolvedValue(CURRENT_USER);
  });

  afterEach(() => {
    authSessionStore.clear();
    vi.clearAllMocks();
  });

  it("로그인 토큰을 저장한 뒤 /me 표시 이름으로 사용자 정보를 확정한다", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <RemoteAuthHarness />
      </AuthProvider>,
    );

    await user.click(screen.getByRole("button", { name: "데모 로그인" }));

    expect(await screen.findByText("/me 응답 상담사")).toBeVisible();
    expect(loginWithDemoCode).toHaveBeenCalledWith("DEMO-CONSULTANT-001");
    expect(getCurrentUser).toHaveBeenCalledTimes(1);
    expect(authSessionStore.getSession()).toMatchObject({
      accessToken: LOGIN_SESSION.accessToken,
      refreshToken: LOGIN_SESSION.refreshToken,
      user: CURRENT_USER,
    });
  });

  it("ID/PW 세션도 토큰 저장 후 /me 사용자로 확정한다", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <RemoteAuthHarness />
      </AuthProvider>,
    );

    await user.click(screen.getByRole("button", { name: "비밀번호 로그인" }));

    expect(await screen.findByText("/me 응답 상담사")).toBeVisible();
    expect(loginWithPassword).toHaveBeenCalledWith(
      "consultant",
      "safe-password",
    );
    expect(getCurrentUser).toHaveBeenCalledTimes(1);
  });

  it("저장된 원격 세션도 토큰을 유지하며 /me 사용자로 다시 동기화한다", async () => {
    authSessionStore.setSession({
      ...LOGIN_SESSION,
      user: { ...LOGIN_USER, displayName: "저장된 이전 이름" },
    });

    render(
      <AuthProvider>
        <RemoteAuthHarness />
      </AuthProvider>,
    );

    expect(await screen.findByText("/me 응답 상담사")).toBeVisible();
    expect(getCurrentUser).toHaveBeenCalledTimes(1);
    expect(authSessionStore.getSession()).toMatchObject({
      accessToken: LOGIN_SESSION.accessToken,
      refreshToken: LOGIN_SESSION.refreshToken,
      user: CURRENT_USER,
    });
  });
});
