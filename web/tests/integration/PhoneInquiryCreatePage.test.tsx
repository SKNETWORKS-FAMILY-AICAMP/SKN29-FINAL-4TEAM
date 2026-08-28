import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";

const CONSULTANT_USER = {
  id: "00000000-0000-4000-8000-000000000102",
  displayName: "전화 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

const CANDIDATE = {
  customer_id: "00000000-0000-4000-8000-000000000001",
  customer_display_name: "합성 전화 고객 1",
  phone_masked: "010-****-0001",
  subscription_id: "00000000-0000-4000-8000-000000000002",
  subscription_status: "ACTIVE",
  management_type_code: "VISIT_CARE",
  product_id: "00000000-0000-4000-8000-000000000003",
  product_model_code: "WPUJAC104DWH",
  product_name: "초소형 직수 정수기",
} as const;

const CREATED_INQUIRY_ID = "00000000-0000-4000-8000-000000000010";

function apiResponse(data: unknown, status = 200) {
  return new Response(
    JSON.stringify({
      success: status < 400,
      data: status < 400 ? data : null,
      error:
        status < 400
          ? null
          : {
              code: status === 404 ? "NOT_FOUND" : "API_ERROR",
              message: status === 404 ? "구독을 찾을 수 없습니다." : "요청 실패",
              details: {},
            },
      metadata: { correlation_id: `corr-${status}` },
    }),
    {
      status,
      headers: { "Content-Type": "application/json" },
    },
  );
}

function createSuccessfulFetchMock() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/consultant/customer-subscriptions/search")) {
      return apiResponse({ items: [CANDIDATE], returned_count: 1 });
    }
    if (url.endsWith("/consultant/phone-inquiries")) {
      return apiResponse(
        {
          inquiry_id: CREATED_INQUIRY_ID,
          inquiry_code: "INQ-20260812-0001",
          status_code: "CONSULTATION_REQUIRED",
          state_version: 1,
          idempotent_replay: false,
          allowed_actions: [],
        },
        201,
      );
    }
    throw new Error(`예상하지 못한 요청: ${url}`);
  });
}

function renderPage() {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={["/consultant/phone-inquiries/new"]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

async function searchAndSelectCandidate(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole("combobox", { name: "고객명 또는 연락처 *" }), "0001");
  const option = await screen.findByRole("option", { name: /합성 전화 고객 1/ });
  expect(option).toHaveTextContent("010-****-0001");
  expect(option).toHaveTextContent(
    "WPUJAC104DWH · 초소형 직수 정수기",
  );
  expect(option).toHaveTextContent("이용 중");
  expect(option).not.toHaveTextContent("010-1234-0001");
  await user.click(option);
}

beforeEach(() => {
  const values = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: storage,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PhoneInquiryCreatePage", () => {
  it("전화 문의 등록 화면에서도 공통 문의 건수를 표시한다", async () => {
    renderPage();

    expect(
      await screen.findByRole("tab", { name: "전체 문의90" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("tab", { name: "새 문의30" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "처리 중인 문의30" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "처리 완료된 문의30" }),
    ).toBeInTheDocument();
  });

  it("이름·연락처 검색을 JSON Body로 보내고 활성 구독 후보를 선택한다", async () => {
    const fetchMock = createSuccessfulFetchMock();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByRole("tab", { name: "전화 문의 등록" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("button", { name: "전화 문의 등록" })).toBeDisabled();

    await searchAndSelectCandidate(user);

    const selected = screen.getByRole("region", { name: "고객 정보" });
    expect(within(selected).getByText("합성 전화 고객 1")).toBeInTheDocument();
    expect(
      within(selected).getByText(
        "WPUJAC104DWH · 초소형 직수 정수기",
      ),
    ).toBeInTheDocument();
    expect(within(selected).getByText("방문 관리")).toBeInTheDocument();
    expect(within(selected).queryByText("VISIT_CARE")).not.toBeInTheDocument();
    expect(screen.queryByText("긴급도 *")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "전화 문의 등록" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("신규 접수")).not.toBeInTheDocument();
    expect(
      screen.queryByText("고객과 구독을 먼저 확인해 주세요"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "등록 전 확인" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("전화 문의 등록 안내"),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("상담 내용")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/상담 기록 저장 기능 연결 후/),
    ).not.toBeInTheDocument();

    const [searchUrl, searchOptions] = fetchMock.mock.calls[0];
    expect(String(searchUrl)).toBe(
      "/api/v1/consultant/customer-subscriptions/search",
    );
    expect(searchOptions?.method).toBe("POST");
    expect(JSON.parse(String(searchOptions?.body))).toEqual({ query: "0001", limit: 10 });
    expect(new Headers(searchOptions?.headers).get("X-Correlation-ID")).toBeTruthy();
  });

  it("선택한 subscription_id와 계약 필드만 전송하고 생성 문의로 연결한다", async () => {
    const fetchMock = createSuccessfulFetchMock();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await searchAndSelectCandidate(user);

    await user.selectOptions(screen.getByLabelText("대표 증상 *"), "LEAK");
    await user.type(
      screen.getByLabelText(/문의 내용/),
      "전화로 접수한 누수 문의입니다.",
    );
    await user.click(screen.getByRole("button", { name: "전화 문의 등록" }));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("INQ-20260812-0001");
    expect(screen.getByRole("link", { name: "문의 상세 보기" })).toHaveAttribute(
      "href",
      `/consultant/inquiries?inquiryId=${CREATED_INQUIRY_ID}`,
    );
    expect(screen.getByRole("button", { name: "새 문의 등록" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "입력 초기화" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "전화 문의 등록" })).not.toBeInTheDocument();

    const [, registerOptions] = fetchMock.mock.calls[1];
    expect(JSON.parse(String(registerOptions?.body))).toEqual({
      subscription_id: CANDIDATE.subscription_id,
      raw_text: "전화로 접수한 누수 문의입니다.",
      representative_symptom_code: "LEAK",
      priority_code: "NORMAL",
    });
    const headers = new Headers(registerOptions?.headers);
    expect(headers.get("X-Correlation-ID")).toBeTruthy();
    expect(headers.get("Idempotency-Key")).toBeTruthy();
    expect(window.localStorage.getItem("waterbridge.phone-inquiry-records.v1")).toBeNull();
  });

  it("등록 404에서는 입력을 유지하고 무효가 된 고객 선택만 초기화한다", async () => {
    const fetchMock = createSuccessfulFetchMock();
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/consultant/customer-subscriptions/search")) {
        return apiResponse({ items: [CANDIDATE], returned_count: 1 });
      }
      return apiResponse(null, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage();
    await searchAndSelectCandidate(user);

    await user.selectOptions(screen.getByLabelText("대표 증상 *"), "LEAK");
    await user.type(screen.getByLabelText(/문의 내용/), "선택 무효 확인용 문의");
    await user.click(screen.getByRole("button", { name: "전화 문의 등록" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "선택한 구독이 더 이상 유효하지 않습니다",
    );
    expect(screen.queryByRole("region", { name: "고객 정보" })).not.toBeInTheDocument();
    expect(screen.getByLabelText(/문의 내용/)).toHaveValue("선택 무효 확인용 문의");
    expect(screen.getByRole("button", { name: "전화 문의 등록" })).toBeDisabled();
  });

  it("등록 후 새 문의 등록을 누르면 고객 선택과 입력값을 초기화한다", async () => {
    vi.stubGlobal("fetch", createSuccessfulFetchMock());
    const user = userEvent.setup();
    renderPage();
    await searchAndSelectCandidate(user);

    await user.selectOptions(screen.getByLabelText("대표 증상 *"), "LEAK");
    await user.type(
      screen.getByLabelText(/문의 내용/),
      "초기화 확인용 상담 기록",
    );
    await user.click(screen.getByRole("button", { name: "전화 문의 등록" }));
    await user.click(await screen.findByRole("button", { name: "새 문의 등록" }));

    expect(screen.queryByRole("region", { name: "고객 정보" })).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "고객명 또는 연락처 *" })).toHaveValue("");
    expect(screen.getByLabelText("대표 증상 *")).toHaveValue("");
    expect(screen.getByLabelText(/문의 내용/)).toHaveValue("");
    expect(screen.getByRole("button", { name: "전화 문의 등록" })).toBeDisabled();
  });
});
