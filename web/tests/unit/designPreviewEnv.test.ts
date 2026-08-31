import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthSession } from "../../src/features/auth/model/authSession";

const PRODUCTION_SESSION_KEY = "waterbridge.auth.session.v1";
const PREVIEW_SESSION_KEY = "waterbridge.auth.preview.session.v1";
const productionSession: AuthSession = {
  accessToken: "test-production-access",
  refreshToken: "test-production-refresh",
  accessExpiresIn: 3600,
  refreshExpiresIn: 604800,
  user: {
    id: "test-production-consultant",
    displayName: "운영 상담사",
    roleCode: "CONSULTANT",
    isActive: true,
  },
};

function configureDesignEnvironment() {
  vi.stubEnv("MODE", "design");
  vi.stubEnv("DEV", true);
  vi.stubEnv("PROD", false);
  vi.stubEnv("VITE_API_BASE_URL", "https://production.example.test/api/v1");
  vi.stubEnv("VITE_USE_MOCK_API", "true");
  vi.stubEnv("VITE_MOCK_AUTHENTICATED", "false");
  vi.stubEnv("VITE_MOCK_ROLE", "OPERATOR");
  vi.stubEnv("VITE_ENABLE_DESIGN_MOCK_FALLBACK", "true");
}

function createStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => void values.delete(key),
    setItem: (key, value) => void values.set(key, String(value)),
  };
}

const originalStorage = Object.getOwnPropertyDescriptor(window, "localStorage");

beforeEach(() => {
  vi.resetModules();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: createStorage(),
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
  if (originalStorage) {
    Object.defineProperty(window, "localStorage", originalStorage);
  }
});

describe("배포 화면을 사용하는 로컬 디자인 환경", () => {
  it("샘플 로그인만 허용하고 기존 Mock 화면·오류 시 Mock 전환을 강제로 끈다", async () => {
    configureDesignEnvironment();

    const { appEnv } = await import("../../src/app/config/env");

    expect(appEnv).toMatchObject({
      isDesignPreview: true,
      useMockApi: false,
      mockAuthenticated: true,
      mockRole: "CONSULTANT",
      apiBaseUrl: "/api/v1",
      enableDesignMockFallback: false,
    });
  });

  it.each([
    "https://production.example.test/api/v1",
    "//production.example.test/api/v1",
    "http://127.0.0.1:8000/api/v1",
    "invalid-base-url",
  ])("외부/오류 API 설정 %s도 디자인에서는 로컬 경로로 고정한다", async (baseUrl) => {
    configureDesignEnvironment();
    vi.stubEnv("VITE_API_BASE_URL", baseUrl);

    const { appEnv } = await import("../../src/app/config/env");

    expect(appEnv.apiBaseUrl).toBe("/api/v1");
    expect(appEnv.useMockApi).toBe(false);
  });

  it("일반 개발 모드의 실제 API 연결 설정은 바꾸지 않는다", async () => {
    configureDesignEnvironment();
    vi.stubEnv("MODE", "development");
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_ENABLE_DESIGN_MOCK_FALLBACK", "false");

    const { appEnv } = await import("../../src/app/config/env");

    expect(appEnv).toMatchObject({
      isDesignPreview: false,
      useMockApi: false,
      mockAuthenticated: false,
      mockRole: "OPERATOR",
      apiBaseUrl: "https://production.example.test/api/v1",
    });
  });

  it("Production은 mode 이름이 design이어도 미리보기 인증·로컬 API를 강제하지 않는다", async () => {
    configureDesignEnvironment();
    vi.stubEnv("DEV", false);
    vi.stubEnv("PROD", true);
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    vi.stubEnv("VITE_ENABLE_DESIGN_MOCK_FALLBACK", "false");

    const { appEnv } = await import("../../src/app/config/env");

    expect(appEnv).toMatchObject({
      isDesignPreview: false,
      useMockApi: false,
      mockAuthenticated: false,
      mockRole: "OPERATOR",
      apiBaseUrl: "https://production.example.test/api/v1",
    });
  });

  it("미리보기 세션 저장·삭제가 기존 운영 로그인 저장소를 읽거나 덮어쓰지 않는다", async () => {
    configureDesignEnvironment();
    const serializedProductionSession = JSON.stringify(productionSession);
    window.localStorage.setItem(PRODUCTION_SESSION_KEY, serializedProductionSession);

    const { authSessionStore } = await import(
      "../../src/features/auth/model/authSession"
    );

    expect(authSessionStore.getSession()).toBeNull();
    const previewSession = {
      ...productionSession,
      accessToken: "mock-access-CONSULTANT-preview",
      refreshToken: "mock-refresh-CONSULTANT-preview",
      user: { ...productionSession.user, id: "preview-consultant" },
    };
    authSessionStore.setSession(previewSession);
    expect(window.localStorage.getItem(PREVIEW_SESSION_KEY)).toBe(
      JSON.stringify(previewSession),
    );
    expect(window.localStorage.getItem(PRODUCTION_SESSION_KEY)).toBe(
      serializedProductionSession,
    );

    authSessionStore.clear();

    expect(window.localStorage.getItem(PREVIEW_SESSION_KEY)).toBeNull();
    expect(window.localStorage.getItem(PRODUCTION_SESSION_KEY)).toBe(
      serializedProductionSession,
    );
  });

  it("일반 운영 모드는 미리보기 세션 대신 기존 운영 세션만 복원한다", async () => {
    vi.stubEnv("MODE", "production");
    vi.stubEnv("DEV", false);
    vi.stubEnv("PROD", true);
    vi.stubEnv("VITE_USE_MOCK_API", "false");
    window.localStorage.setItem(PRODUCTION_SESSION_KEY, JSON.stringify(productionSession));
    window.localStorage.setItem(
      PREVIEW_SESSION_KEY,
      JSON.stringify({ ...productionSession, accessToken: "mock-access-preview" }),
    );

    const { authSessionStore } = await import(
      "../../src/features/auth/model/authSession"
    );

    expect(authSessionStore.getAccessToken()).toBe(productionSession.accessToken);
    authSessionStore.clear();
    expect(window.localStorage.getItem(PREVIEW_SESSION_KEY)).not.toBeNull();
  });
});
