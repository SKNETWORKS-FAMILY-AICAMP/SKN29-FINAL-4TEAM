import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, getApiErrorKind } from "../../src/common/api/apiError";
import { requestApi } from "../../src/common/api/httpClient";
import { getTotalPages, normalizePageInfo } from "../../src/common/api/pagination";
import { createRequestContext } from "../../src/common/api/requestContext";

afterEach(() => {
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
