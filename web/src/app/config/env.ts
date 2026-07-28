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

export const appEnv = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  useMockApi: readBoolean(import.meta.env.VITE_USE_MOCK_API, true),
  mockAuthenticated: readBoolean(
    import.meta.env.VITE_MOCK_AUTHENTICATED,
    true,
  ),
  mockRole: readRole(import.meta.env.VITE_MOCK_ROLE),
} as const;
