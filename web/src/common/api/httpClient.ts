import { appEnv } from "../../app/config/env";
import {
  ApiClientError,
  getApiErrorKind,
  type ApiErrorPayload,
} from "./apiError";
import { isApiResponse, type ApiResponse } from "./apiResponse";
import type { RequestContext } from "./requestContext";

const DEFAULT_TIMEOUT_MS = 10_000;

export interface ApiRequestOptions
  extends Omit<RequestInit, "body" | "headers" | "signal"> {
  accessToken?: string;
  body?: unknown;
  headers?: Record<string, string>;
  requestContext?: RequestContext;
  timeoutMs?: number;
}

function createUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;

  const baseUrl = appEnv.apiBaseUrl.replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl}${normalizedPath}`;
}

function isApiErrorPayload(value: unknown): value is ApiErrorPayload {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.message === "string" &&
    typeof candidate.details === "object" &&
    candidate.details !== null
  );
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new ApiClientError({
      kind: "PARSE_ERROR",
      status: response.status,
      message: "서버 응답 형식을 확인할 수 없습니다.",
    });
  }

  try {
    return await response.json();
  } catch (cause) {
    throw new ApiClientError({
      kind: "PARSE_ERROR",
      status: response.status,
      message: "서버 JSON 응답을 해석하지 못했습니다.",
      cause,
    });
  }
}

export async function requestApi<TData>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<ApiResponse<TData>> {
  const {
    accessToken,
    body,
    headers: headerValues,
    requestContext,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    ...requestInit
  } = options;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers = new Headers(headerValues);
  headers.set("Accept", "application/json");

  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (requestContext) {
    Object.entries(requestContext.headers).forEach(([key, value]) => {
      headers.set(key, value);
    });
  }

  try {
    const response = await fetch(createUrl(path), {
      ...requestInit,
      body: body === undefined ? undefined : JSON.stringify(body),
      headers,
      signal: controller.signal,
    });
    const payload = await parseResponse(response);

    if (!isApiResponse(payload)) {
      throw new ApiClientError({
        kind: "PARSE_ERROR",
        status: response.status,
        message: "공통 API 응답 구조와 일치하지 않습니다.",
      });
    }

    const typedPayload = payload as ApiResponse<TData>;
    if (!response.ok || !typedPayload.success || typedPayload.error) {
      const error = isApiErrorPayload(typedPayload.error)
        ? typedPayload.error
        : {
            code: "UNKNOWN_ERROR",
            message: "요청 처리 중 오류가 발생했습니다.",
            details: {},
          };

      throw new ApiClientError({
        kind: getApiErrorKind(response.status),
        status: response.status,
        code: error.code,
        message: error.message,
        details: error.details,
        correlationId: typedPayload.metadata.correlation_id,
      });
    }

    return typedPayload;
  } catch (caught) {
    if (caught instanceof ApiClientError) throw caught;

    if (caught instanceof DOMException && caught.name === "AbortError") {
      throw new ApiClientError({
        kind: "TIMEOUT",
        message: "요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
        cause: caught,
      });
    }

    throw new ApiClientError({
      kind: "NETWORK_ERROR",
      message: "네트워크에 연결하지 못했습니다.",
      cause: caught,
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}
