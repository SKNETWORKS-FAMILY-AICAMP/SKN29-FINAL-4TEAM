import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { useAuth } from "../../src/app/providers/authContext";
import { requestApi } from "../../src/common/api/httpClient";
import { authSessionStore } from "../../src/features/auth/model/authSession";

const CONSULTANT_USER = {
  id: "00000000-0000-4000-8000-000000000102",
  displayName: "테스트 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

function createLocalStorageMock(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => void values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

function AuthHarness() {
  const auth = useAuth();

  if (!auth.user) return <p>로그인 필요</p>;
  return (
    <>
      <p>{auth.user.displayName}</p>
      <button type="button" onClick={() => void auth.signOut()}>
        로그아웃
      </button>
      <button
        type="button"
        onClick={() => void requestApi("/protected").catch(() => undefined)}
      >
        보호 API 호출
      </button>
    </>
  );
}

describe("AuthProvider 통합", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: createLocalStorageMock(),
    });
    authSessionStore.clear();
  });
  afterEach(() => {
    authSessionStore.clear();
    vi.restoreAllMocks();
  });

  it("로그아웃하면 메모리 토큰과 사용자 상태를 함께 지운다", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider initialUser={CONSULTANT_USER}>
        <AuthHarness />
      </AuthProvider>,
    );
    await screen.findByText("테스트 상담원");

    await user.click(screen.getByRole("button", { name: "로그아웃" }));

    expect(await screen.findByText("로그인 필요")).toBeInTheDocument();
    expect(authSessionStore.getSession()).toBeNull();
    expect(window.localStorage.getItem("waterbridge.auth.session.v1")).toBeNull();
  });

  it("로그인 세션을 새로고침 복원용 저장소에 유지한다", async () => {
    render(
      <AuthProvider initialUser={CONSULTANT_USER}>
        <AuthHarness />
      </AuthProvider>,
    );

    await screen.findByText("테스트 상담원");
    expect(window.localStorage.getItem("waterbridge.auth.session.v1")).toContain(
      CONSULTANT_USER.id,
    );
  });

  it("401 갱신 후 재시도도 실패하면 로그인 상태를 제거한다", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(
          JSON.stringify({ code: "AUTH-01", message: "인증이 필요합니다." }),
          { status: 401, headers: { "Content-Type": "application/json" } },
        ),
    );
    render(
      <AuthProvider initialUser={CONSULTANT_USER}>
        <AuthHarness />
      </AuthProvider>,
    );
    await screen.findByText("테스트 상담원");

    await user.click(screen.getByRole("button", { name: "보호 API 호출" }));

    expect(await screen.findByText("로그인 필요")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(authSessionStore.getSession()).toBeNull();
  });
});
