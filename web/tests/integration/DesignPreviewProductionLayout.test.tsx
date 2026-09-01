import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.hoisted(() => {
  vi.stubEnv("MODE", "design");
  vi.stubEnv("DEV", true);
  vi.stubEnv("PROD", false);
  // Conflicting settings must not switch design mode to the legacy Mock UI
  // or send requests to a real deployment.
  vi.stubEnv("VITE_USE_MOCK_API", "true");
  vi.stubEnv("VITE_MOCK_AUTHENTICATED", "false");
  vi.stubEnv("VITE_API_BASE_URL", "https://production.example.test/api/v1");
  vi.stubEnv("VITE_ENABLE_DESIGN_MOCK_FALLBACK", "true");
});

import {
  createDesignPreviewApi,
  DESIGN_PREVIEW_INQUIRY_IDS,
} from "../../preview/designPreviewApi";
import App from "../../src/app/App";
import { appEnv } from "../../src/app/config/env";
import { authSessionStore } from "../../src/features/auth/model/authSession";
import { consultantWorkspaceDataRepository } from "../../src/features/consultation/repositories/consultantWorkspaceDataRepository";

interface ObservedRequest {
  url: string;
  method: string;
  status: number;
  authorization: string | null;
}

const observedRequests: ObservedRequest[] = [];
const originalStorage = Object.getOwnPropertyDescriptor(window, "localStorage");
const productionSession = JSON.stringify({
  accessToken: "test-existing-production-token",
  refreshToken: "test-existing-production-refresh-token",
  accessExpiresIn: 3600,
  refreshExpiresIn: 604800,
  user: {
    id: "test-production-user",
    displayName: "기존 운영 로그인",
    roleCode: "CONSULTANT",
    isActive: true,
  },
});

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

function renderAt(path: string) {
  window.history.replaceState({}, "", path);
  return render(<App />);
}

beforeEach(() => {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: createStorage(),
  });
  authSessionStore.clear();
  window.localStorage.setItem("waterbridge.auth.session.v1", productionSession);
  observedRequests.length = 0;
  const handle = createDesignPreviewApi();
  // Only the HTTP transport is substituted. App, authentication, repositories,
  // DTO mappers, route components, and shared production styles stay real.
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string"
      ? input
      : input instanceof URL ? input.href : input.url;
    expect(url).toMatch(/^\/api\/v1\//);
    const method = init?.method ?? "GET";
    const headers = new Headers(init?.headers);
    const response = handle({
      url,
      method,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
      headers: Object.fromEntries(headers.entries()),
    });
    observedRequests.push({
      url,
      method,
      status: response.status,
      authorization: headers.get("Authorization"),
    });
    return new Response(JSON.stringify(response.body), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  }));
});

afterEach(() => {
  cleanup();
  expect(observedRequests.length).toBeGreaterThan(0);
  expect(observedRequests.every(({ url }) => url.startsWith("/api/v1/"))).toBe(true);
  expect(observedRequests.some(({ url }) => url.includes("/auth/"))).toBe(false);
  expect(observedRequests.some(({ authorization }) => authorization?.includes("test-existing-production-token"))).toBe(false);
  expect(window.localStorage.getItem("waterbridge.auth.session.v1")).toBe(productionSession);
  authSessionStore.clear();
  vi.unstubAllGlobals();
});

afterAll(() => {
  vi.unstubAllEnvs();
  if (originalStorage) {
    Object.defineProperty(window, "localStorage", originalStorage);
  }
});

describe("디자인 미리보기의 배포용 화면 공통 사용", () => {
  it("실제 App에서 대시보드 → 목록 → REMOTE 상세 3단계를 같은 화면 구성으로 연다", async () => {
    const user = userEvent.setup();
    renderAt("/consultant/dashboard");

    expect(appEnv.isDesignPreview).toBe(true);
    expect(appEnv.useMockApi).toBe(false);
    expect(consultantWorkspaceDataRepository.dataSource).toBe("REMOTE");
    expect(await screen.findByRole("button", { name: "전체 문의 수15" })).toBeVisible();
    expect(screen.getByRole("button", { name: "새 문의3" })).toBeVisible();
    expect(screen.getByRole("button", { name: "처리 중인 문의8" })).toBeVisible();
    expect(screen.getByRole("button", { name: "처리 완료된 문의4" })).toBeVisible();
    expect(window.localStorage.getItem("waterbridge.auth.preview.session.v1")).toContain("mock-access-");

    await user.click(screen.getByRole("tab", { name: "전체 문의15" }));
    await user.click(await screen.findByTestId(`consultant-inquiry-${DESIGN_PREVIEW_INQUIRY_IDS.new}`));

    const dialog = await screen.findByRole("dialog");
    for (const name of [
      "상담 1단계: 고객 문의 · 제품 확인",
      "상담 2단계: AI 상담 · 이전 상담 기록 확인",
      "상담 3단계: 상담 진행",
    ]) {
      expect(await within(dialog).findByRole("button", { name })).toBeVisible();
    }
    expect(within(dialog).getByLabelText("상담 문의 상세")).toBeInTheDocument();
    expect(within(dialog).queryByLabelText("선택 문의 처리")).not.toBeInTheDocument();
    expect(observedRequests).toContainEqual(expect.objectContaining({
      url: `/api/v1/inquiries/${DESIGN_PREVIEW_INQUIRY_IDS.new}`,
      status: 200,
    }));
  });

  it("처리 중인 샘플 상세에서도 배포용 AI·이전 상담 및 수정 입력 화면을 확인한다", async () => {
    const user = userEvent.setup();
    renderAt(`/consultant/inquiries?bucket=IN_PROGRESS&inquiryId=${DESIGN_PREVIEW_INQUIRY_IDS.inProgress}`);
    const dialog = await screen.findByRole("dialog");

    await user.click(await within(dialog).findByRole("button", {
      name: "상담 2단계: AI 상담 · 이전 상담 기록 확인",
    }));
    expect(within(dialog).getByRole("heading", { name: "고객에게 안내할 내용" })).toBeVisible();

    await user.click(within(dialog).getByRole("button", { name: "상담 3단계: 상담 진행" }));
    expect(within(dialog).getByLabelText("상담 기록")).toBeVisible();
    expect(within(dialog).getByLabelText("상담 기록")).toBeDisabled();
    expect(within(dialog).queryByLabelText("상담 내용 수정본")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "편집 시작" }));
    expect(within(dialog).getByLabelText("상담 기록")).toBeEnabled();
    expect(within(dialog).getByRole("button", { name: "수정 내용 저장" })).toBeVisible();
    expect(observedRequests.every(({ method }) => method === "GET")).toBe(true);
  });

  it("공지 메뉴의 실제 페이지네이션·상세 이동을 샘플 API로 유지한다", async () => {
    const user = userEvent.setup();
    renderAt("/consultant/notices");

    expect(await screen.findByRole("tab", { name: "전체 문의15" })).toBeVisible();
    expect(await screen.findByRole("navigation", { name: "공지사항 목록 페이지" })).toBeVisible();
    await user.click(await screen.findByRole("button", { name: /긴급 문의 응대 절차 안내/ }));

    expect(await screen.findByRole("heading", { name: "공지사항 상세" })).toBeVisible();
    expect(await screen.findByRole("heading", { name: "긴급 문의 응대 절차 안내" })).toBeVisible();
    expect(observedRequests).toContainEqual(expect.objectContaining({
      url: "/api/v1/consultant/notices/notice-emergency-001",
      status: 200,
    }));
    await user.click(screen.getByRole("button", { name: /공지사항 목록으로/ }));
    expect(await screen.findByRole("navigation", { name: "공지사항 목록 페이지" })).toBeVisible();
  });

  it("전화 문의 입력 레이아웃과 검색 결과는 확인하되 등록은 로컬에서 차단한다", async () => {
    const user = userEvent.setup();
    renderAt("/consultant/phone-inquiries/new");

    expect(await screen.findByRole("tab", { name: "전체 문의15" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "전화 문의 등록" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "등록 전 확인" })).not.toBeInTheDocument();
    await user.type(screen.getByRole("combobox", { name: "고객명 또는 연락처 *" }), "0001");
    await user.click(await screen.findByRole("option", { name: /김민준/ }));
    expect(within(screen.getByRole("region", { name: "고객 정보" })).getByText("김민준")).toBeVisible();
    await user.click(screen.getByRole("combobox", { name: "대표 증상 *" }));
    await user.click(screen.getByRole("option", { name: "누수" }));
    await user.type(screen.getByLabelText(/문의 내용/), "로컬 화면의 입력 디자인 확인입니다.");
    await user.click(screen.getByRole("button", { name: "전화 문의 등록" }));

    await waitFor(() => expect(observedRequests).toContainEqual(expect.objectContaining({
      url: "/api/v1/consultant/phone-inquiries",
      method: "POST",
      status: 405,
    })));
    expect(screen.getByLabelText(/문의 내용/)).toHaveValue("로컬 화면의 입력 디자인 확인입니다.");
    expect(screen.queryByText("전화 문의가 등록되었습니다.")).not.toBeInTheDocument();
    expect(observedRequests.some(({ method, status }) => method !== "GET" && status === 201)).toBe(false);
  });
});
