import { describe, expect, it } from "vitest";

import { readApiBaseUrl } from "../../src/app/config/env";

describe("Web 환경변수", () => {
  it("상대·절대 API Base URL을 정규화한다", () => {
    expect(readApiBaseUrl(undefined)).toBe("/api/v1");
    expect(readApiBaseUrl("/api/v1/")).toBe("/api/v1");
    expect(readApiBaseUrl("https://api.example.com/api/v1/")).toBe(
      "https://api.example.com/api/v1",
    );
  });

  it("잘못된 API Base URL이면 시작 단계에서 실패한다", () => {
    expect(() => readApiBaseUrl("api/v1")).toThrow("VITE_API_BASE_URL");
    expect(() => readApiBaseUrl("ftp://api.example.com")).toThrow(
      "VITE_API_BASE_URL",
    );
  });
});
