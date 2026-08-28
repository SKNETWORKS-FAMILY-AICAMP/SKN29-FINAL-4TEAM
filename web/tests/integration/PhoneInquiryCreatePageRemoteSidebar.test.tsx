import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../src/app/config/env", async () => {
  const actual = await vi.importActual<
    typeof import("../../src/app/config/env")
  >("../../src/app/config/env");

  return {
    ...actual,
    appEnv: {
      ...actual.appEnv,
      enableDesignMockFallback: false,
      mockAuthenticated: false,
      useMockApi: false,
    },
  };
});

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";

const CONSULTANT_USER = {
  id: "00000000-0000-4000-8000-000000000102",
  displayName: "전화 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

function emptyInquiryListResponse() {
  return new Response(
    JSON.stringify({
      success: true,
      data: {
        items: [],
        page_info: { page: 1, size: 100, total: 0 },
        status_counts: {},
      },
      error: null,
      metadata: { correlation_id: "corr-empty-sidebar" },
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/inquiries?")) {
        return emptyInquiryListResponse();
      }
      throw new Error(`예상하지 못한 요청: ${url}`);
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PhoneInquiryCreatePage Remote 사이드바", () => {
  it(
    "Backend 문의가 0건이면 디자인 Mock 대신 실제 0건을 유지한다",
    async () => {
      render(
        <AuthProvider initialUser={CONSULTANT_USER}>
          <MemoryRouter initialEntries={["/consultant/phone-inquiries/new"]}>
            <AppRoutes />
          </MemoryRouter>
        </AuthProvider>,
      );

      expect(
        await screen.findByRole("tab", { name: "전체 문의0" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("tab", { name: "새 문의0" }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("tab", { name: "처리 중인 문의0" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("tab", { name: "처리 완료된 문의0" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("tab", { name: "전체 문의90" }),
      ).not.toBeInTheDocument();
    },
    10_000,
  );
});
