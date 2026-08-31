import { afterEach, describe, expect, it, vi } from "vitest";

import * as httpClient from "../../src/common/api/httpClient";
import { loginWithPassword, revokeRefreshToken } from "../../src/features/auth/api/authApi";

afterEach(() => vi.restoreAllMocks());

describe("인증 API", () => {
  it("아이디와 비밀번호 대소문자를 변환하지 않고 인증 서버로 전달한다", async () => {
    const request = vi.spyOn(httpClient, "requestApi").mockResolvedValue({
      data: {
        access_token: "test-access", refresh_token: "test-refresh", token_type: "Bearer",
        access_expires_in: 60, refresh_expires_in: 600,
        user: { id: "test-consultant", display_name: "테스트 상담사", role_code: "CONSULTANT", is_active: true, customer_profile: null, allowed_actions: [] },
      },
      status: 200,
    });

    await loginWithPassword("Counselor-Aa", "Test-Pass_Aa1!");
    await loginWithPassword("counselor-aa", "test-pass_aa1!");

    expect(request).toHaveBeenNthCalledWith(1, "/auth/login", {
      method: "POST", auth: "none",
      body: { username: "Counselor-Aa", password: "Test-Pass_Aa1!" },
    });
    expect(request).toHaveBeenNthCalledWith(2, "/auth/login", {
      method: "POST", auth: "none",
      body: { username: "counselor-aa", password: "test-pass_aa1!" },
    });
  });

  it("로그아웃은 refresh token을 인증 헤더 없이 폐기 요청한다", async () => {
    const request = vi
      .spyOn(httpClient, "requestApi")
      .mockResolvedValue({ data: { revoked: true }, status: 200 });

    await revokeRefreshToken("refresh-token");

    expect(request).toHaveBeenCalledWith("/auth/logout", {
      method: "POST",
      auth: "none",
      body: { refresh_token: "refresh-token" },
    });
  });
});
