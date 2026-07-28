import type { ApiErrorPayload } from "./apiError";

export interface ApiMetadata {
  correlation_id: string;
}

export interface ApiResponse<TData> {
  success: boolean;
  data: TData | null;
  error: ApiErrorPayload | null;
  metadata: ApiMetadata;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isApiResponse(value: unknown): value is ApiResponse<unknown> {
  if (!isRecord(value) || typeof value.success !== "boolean") return false;
  if (!("data" in value) || !("error" in value)) return false;
  if (!isRecord(value.metadata)) return false;

  return typeof value.metadata.correlation_id === "string";
}
