import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, getApiErrorKind } from "../../src/common/api/apiError";
import {
  configureApiAuth,
  requestApi,
} from "../../src/common/api/httpClient";
import { getTotalPages, normalizePageInfo } from "../../src/common/api/pagination";
import { createRequestContext } from "../../src/common/api/requestContext";

afterEach(() => {
  configureApiAuth(null);
  vi.unstubAllGlobals();
});

describe("공통 API 기반", () => {
  it("계약된 HTTP 상태를 화면 오류 종류로 구분한다", () => {
    expect(getApiErrorKind(401)).toBe("UNAUTHORIZED");
    expect(getApiErrorKind(403)).toBe("FORBIDDEN");
    expect(getApiErrorKind(404)).toBe("NOT_FOUND");
    expect(getApiErrorKind(409)).toBe("CONFLICT");
    expect(getApiErrorKind(422)).toBe("VALIDATION_ERROR");
    expect(getApiErrorKind(503)).toBe("SERVER_ERROR");
  });

  it("PageInfo 계약을 안전한 범위로 정규화한다", () => {
    const pageInfo = normalizePageInfo({ page: 0, size: 250, total: -3 });

    expect(pageInfo).toEqual({ page: 1, size: 100, total: 0 });
    expect(getTotalPages({ page: 1, size: 2, total: 5 })).toBe(3);
  });

  it("공통 응답과 추적·멱등 Header를 사용한다", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          data: { inquiry_id: "f72a3b18-a4f8-5f5e-8c86-199ffc1d8aa2" },
          error: null,
          metadata: { correlation_id: "00000000-0000-4000-8000-000000000001" },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const context = createRequestContext();

    const result = await requestApi<{ inquiry_id: string }>("/test", {
      method: "POST",
      body: { state_version: 1 },
      requestContext: context,
    });

    expect(result.data?.inquiry_id).toBe(
      "f72a3b18-a4f8-5f5e-8c86-199ffc1d8aa2",
    );
    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = request.headers as Headers;
    expect(headers.get("X-Correlation-ID")).toBe(context.correlationId);
    expect(headers.get("Idempotency-Key")).toBe(context.idempotencyKey);
  });

  it("메모리 세션의 Access Token을 Authorization Header에 자동 적용한다", async () => {
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(
          JSON.stringify({
            success: true,
            data: { ok: true },
            error: null,
            metadata: { correlation_id: "correlation-auth" },
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    configureApiAuth({
      getAccessToken: () => "session-access-token",
      refreshAccessToken: vi.fn(),
      clearSession: vi.fn(),
    });

    await requestApi("/protected");

    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = request.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer session-access-token");
    expect(headers.get("X-Correlation-ID")).toBeTruthy();
  });

  it("동시에 발생한 401은 Refresh 한 번을 공유하고 원요청을 한 번만 재시도한다", async () => {
    let resolveRefresh: ((token: string) => void) | undefined;
    const refreshAccessToken = vi.fn(
      () =>
        new Promise<string>((resolve) => {
          resolveRefresh = resolve;
        }),
    );
    const clearSession = vi.fn();
    const fetchMock = vi.fn().mockImplementation(
      async (_path: string, init: RequestInit) => {
        const headers = init.headers as Headers;
        const isRefreshed =
          headers.get("Authorization") === "Bearer refreshed-access-token";

        return new Response(
          JSON.stringify(
            isRefreshed
              ? {
                  success: true,
                  data: { ok: true },
                  error: null,
                  metadata: { correlation_id: "correlation-success" },
                }
              : {
                  success: false,
                  data: null,
                  error: {
                    code: "AUTH_REQUIRED",
                    message: "Access Token이 만료되었습니다.",
                    details: {},
                  },
                  metadata: { correlation_id: "correlation-401" },
                },
          ),
          {
            status: isRefreshed ? 200 : 401,
            headers: { "Content-Type": "application/json" },
          },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    configureApiAuth({
      getAccessToken: () => "expired-access-token",
      refreshAccessToken,
      clearSession,
    });

    const pendingRequests = Promise.all([
      requestApi("/protected/one"),
      requestApi("/protected/two"),
    ]);
    await vi.waitFor(() => expect(refreshAccessToken).toHaveBeenCalledTimes(1));
    resolveRefresh?.("refreshed-access-token");
    await pendingRequests;

    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(clearSession).not.toHaveBeenCalled();
    const retryHeaders = fetchMock.mock.calls
      .slice(2)
      .map((call) => (call[1] as RequestInit).headers as Headers);
    expect(
      retryHeaders.every(
        (headers) =>
          headers.get("Authorization") === "Bearer refreshed-access-token",
      ),
    ).toBe(true);
  });

  it("Refresh 후에도 401이면 세션을 제거하고 더 재시도하지 않는다", async () => {
    const clearSession = vi.fn();
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(
          JSON.stringify({
            success: false,
            data: null,
            error: {
              code: "AUTH_REQUIRED",
              message: "인증이 필요합니다.",
              details: {},
            },
            metadata: { correlation_id: "correlation-401" },
          }),
          {
            status: 401,
            headers: { "Content-Type": "application/json" },
          },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    configureApiAuth({
      getAccessToken: () => "expired-access-token",
      refreshAccessToken: vi.fn().mockResolvedValue("still-invalid-token"),
      clearSession,
    });

    await expect(requestApi("/protected")).rejects.toMatchObject({
      kind: "UNAUTHORIZED",
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(clearSession).toHaveBeenCalledTimes(1);
  });

  it("Refresh 자체가 실패하면 세션을 제거하고 원요청을 재시도하지 않는다", async () => {
    const clearSession = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          data: null,
          error: {
            code: "AUTH_REQUIRED",
            message: "인증이 필요합니다.",
            details: {},
          },
          metadata: { correlation_id: "correlation-401" },
        }),
        {
          status: 401,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    configureApiAuth({
      getAccessToken: () => "expired-access-token",
      refreshAccessToken: vi.fn().mockRejectedValue(new Error("refresh failed")),
      clearSession,
    });

    await expect(requestApi("/protected")).rejects.toMatchObject({
      kind: "UNAUTHORIZED",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(clearSession).toHaveBeenCalledTimes(1);
  });

  it("401 자동 재시도에서도 멱등 키를 보존하고 추적 ID는 새로 만든다", async () => {
    let attempt = 0;
    const fetchMock = vi.fn().mockImplementation(async () => {
      attempt += 1;
      return new Response(
        JSON.stringify(
          attempt === 1
            ? {
                success: false,
                data: null,
                error: {
                  code: "AUTH_REQUIRED",
                  message: "Access Token이 만료되었습니다.",
                  details: {},
                },
                metadata: { correlation_id: "correlation-401" },
              }
            : {
                success: true,
                data: { saved: true },
                error: null,
                metadata: { correlation_id: "correlation-success" },
              },
        ),
        {
          status: attempt === 1 ? 401 : 200,
          headers: { "Content-Type": "application/json" },
        },
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    configureApiAuth({
      getAccessToken: () => "expired-access-token",
      refreshAccessToken: vi.fn().mockResolvedValue("refreshed-access-token"),
      clearSession: vi.fn(),
    });
    const context = createRequestContext();

    await requestApi("/protected-write", {
      method: "POST",
      body: { state_version: 3 },
      requestContext: context,
    });

    const initialHeaders = (fetchMock.mock.calls[0][1] as RequestInit)
      .headers as Headers;
    const retryHeaders = (fetchMock.mock.calls[1][1] as RequestInit)
      .headers as Headers;
    expect(retryHeaders.get("Idempotency-Key")).toBe(
      initialHeaders.get("Idempotency-Key"),
    );
    expect(retryHeaders.get("X-Correlation-ID")).not.toBe(
      initialHeaders.get("X-Correlation-ID"),
    );
  });

  it("인증 제외 요청은 Authorization과 401 Refresh를 사용하지 않는다", async () => {
    const refreshAccessToken = vi.fn();
    const clearSession = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          data: null,
          error: {
            code: "AUTH_REQUIRED",
            message: "로그인 정보가 올바르지 않습니다.",
            details: {},
          },
          metadata: { correlation_id: "correlation-login-401" },
        }),
        {
          status: 401,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    configureApiAuth({
      getAccessToken: () => "existing-access-token",
      refreshAccessToken,
      clearSession,
    });

    await expect(
      requestApi("/auth/demo-login", { auth: "none", method: "POST" }),
    ).rejects.toMatchObject({ kind: "UNAUTHORIZED" });

    const headers = (fetchMock.mock.calls[0][1] as RequestInit)
      .headers as Headers;
    expect(headers.get("Authorization")).toBeNull();
    expect(refreshAccessToken).not.toHaveBeenCalled();
    expect(clearSession).not.toHaveBeenCalled();
  });

  it("409 오류에서 공개 오류와 correlation_id를 보존한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            data: null,
            error: {
              code: "STATE-CONFLICT-01",
              message: "최신 상태를 다시 확인해 주세요.",
              details: {
                current_status: "CONSULTATION_IN_PROGRESS",
                current_state_version: 3,
                allowed_actions: ["UPDATE_CONSULTATION_SUMMARY"],
              },
            },
            metadata: {
              correlation_id: "00000000-0000-4000-8000-000000000002",
            },
          }),
          {
            status: 409,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );

    await expect(requestApi("/test")).rejects.toMatchObject<
      Partial<ApiClientError>
    >({
      kind: "CONFLICT",
      code: "STATE-CONFLICT-01",
      correlationId: "00000000-0000-4000-8000-000000000002",
    });
  });

  it("멱등 키 재사용 409의 빈 details를 그대로 보존한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            data: null,
            error: {
              code: "DUPLICATE-EVENT-01",
              message: "같은 키에 다른 요청이 사용되었습니다.",
              details: {},
            },
            metadata: {
              correlation_id: "00000000-0000-4000-8000-000000000003",
            },
          }),
          {
            status: 409,
            headers: { "Content-Type": "application/json" },
          },
        ),
      ),
    );

    await expect(requestApi("/test")).rejects.toMatchObject<
      Partial<ApiClientError>
    >({
      kind: "CONFLICT",
      code: "DUPLICATE-EVENT-01",
      details: {},
      correlationId: "00000000-0000-4000-8000-000000000003",
    });
  });
});
