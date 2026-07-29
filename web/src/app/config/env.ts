import type { AppRole } from "../providers/authContext";

const ROLE_CODES: readonly AppRole[] = [
  "CUSTOMER",
  "CONSULTANT",
  "TECHNICIAN",
  "OPERATOR",
];

function readBoolean(value: string | undefined, fallback: boolean) {
  if (value === undefined || value === "") return fallback;
  if (value === "true") return true;
  if (value === "false") return false;
  throw new Error(`환경변수 boolean 값이 올바르지 않습니다: ${value}`);
}

function readRole(value: string | undefined): AppRole {
  const role = value ?? "CONSULTANT";
  if (ROLE_CODES.includes(role as AppRole)) return role as AppRole;
  throw new Error(`지원하지 않는 Mock 역할입니다: ${role}`);
}

export function readApiBaseUrl(value: string | undefined): string {
  const apiBaseUrl = value?.trim() || "/api/v1";

  if (apiBaseUrl.startsWith("/")) {
    return apiBaseUrl.length > 1 ? apiBaseUrl.replace(/\/+$/, "") : apiBaseUrl;
  }

  try {
    const parsed = new URL(apiBaseUrl);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error();
    }
    return apiBaseUrl.replace(/\/+$/, "");
  } catch {
    throw new Error(
      `VITE_API_BASE_URL은 /로 시작하거나 http(s) URL이어야 합니다: ${apiBaseUrl}`,
    );
  }
}

export const appEnv = {
  apiBaseUrl: readApiBaseUrl(import.meta.env.VITE_API_BASE_URL),
  useMockApi: readBoolean(import.meta.env.VITE_USE_MOCK_API, true),
  mockAuthenticated: readBoolean(
    import.meta.env.VITE_MOCK_AUTHENTICATED,
    true,
  ),
  mockRole: readRole(import.meta.env.VITE_MOCK_ROLE),
} as const;
