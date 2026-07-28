export type ApiErrorKind =
  | "BAD_REQUEST"
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "CONFLICT"
  | "VALIDATION_ERROR"
  | "SERVER_ERROR"
  | "NETWORK_ERROR"
  | "TIMEOUT"
  | "PARSE_ERROR"
  | "UNKNOWN_ERROR";

export interface ApiErrorPayload {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

interface ApiClientErrorOptions {
  kind: ApiErrorKind;
  message: string;
  status?: number;
  code?: string;
  details?: Record<string, unknown>;
  correlationId?: string;
  cause?: unknown;
}

export class ApiClientError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly code?: string;
  readonly details: Record<string, unknown>;
  readonly correlationId?: string;

  constructor(options: ApiClientErrorOptions) {
    super(options.message, { cause: options.cause });
    this.name = "ApiClientError";
    this.kind = options.kind;
    this.status = options.status;
    this.code = options.code;
    this.details = options.details ?? {};
    this.correlationId = options.correlationId;
  }
}

export function getApiErrorKind(status: number): ApiErrorKind {
  if (status === 400) return "BAD_REQUEST";
  if (status === 401) return "UNAUTHORIZED";
  if (status === 403) return "FORBIDDEN";
  if (status === 404) return "NOT_FOUND";
  if (status === 409) return "CONFLICT";
  if (status === 422) return "VALIDATION_ERROR";
  if (status >= 500) return "SERVER_ERROR";
  return "UNKNOWN_ERROR";
}
