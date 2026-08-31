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

export type MockDataset = "REMOTE_PARITY" | "DESIGN_SCENARIOS";

function readMockDataset(value: string | undefined): MockDataset {
  const dataset =
    value ?? (import.meta.env.MODE === "test" ? "DESIGN_SCENARIOS" : "REMOTE_PARITY");
  if (dataset === "REMOTE_PARITY" || dataset === "DESIGN_SCENARIOS") {
    return dataset;
  }
  throw new Error(`지원하지 않는 Mock 데이터셋입니다: ${dataset}`);
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

const isDesignPreview = import.meta.env.DEV && import.meta.env.MODE === "design";

export const appEnv = {
  isDesignPreview,
  // 디자인 미리보기는 같은 출처의 Vite 샘플 API만 사용한다. 로컬 환경변수에
  // 운영 주소가 있어도 실제 고객 데이터나 상태 변경 요청을 보내지 않는다.
  apiBaseUrl: isDesignPreview
    ? "/api/v1"
    : readApiBaseUrl(import.meta.env.VITE_API_BASE_URL),
  // 로컬 개발·Test에서는 명시값이 없을 때만 Mock을 허용한다.
  // Production Build는 환경변수 누락을 Mock 전환으로 해석하지 않는다.
  useMockApi:
    !isDesignPreview &&
    readBoolean(import.meta.env.VITE_USE_MOCK_API, import.meta.env.DEV),
  mockAuthenticated:
    isDesignPreview ||
    readBoolean(import.meta.env.VITE_MOCK_AUTHENTICATED, import.meta.env.DEV),
  mockRole: isDesignPreview
    ? "CONSULTANT"
    : readRole(import.meta.env.VITE_MOCK_ROLE),
  // 디자인 모드도 배포용 REMOTE 화면을 사용하며 데이터만 Vite에서 공급한다.
  // 이 데이터셋 설정은 기존 Mock 테스트/개발 경로에서만 사용한다.
  mockDataset: isDesignPreview
    ? "REMOTE_PARITY"
    : readMockDataset(import.meta.env.VITE_MOCK_DATASET),
  // Backend가 비어 있거나 일부 업무함만 있을 때 디자인용 다건 Mock으로
  // 자동 전환할지 선택한다. 실제 API/E2E에서는 반드시 false로 둔다.
  enableDesignMockFallback:
    !isDesignPreview &&
    readBoolean(import.meta.env.VITE_ENABLE_DESIGN_MOCK_FALLBACK, false),
} as const;
