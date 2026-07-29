import { afterEach, describe, expect, it, vi } from "vitest";

import * as httpClient from "../../src/common/api/httpClient";
import { revokeRefreshToken } from "../../src/features/auth/api/authApi";

afterEach(() => vi.restoreAllMocks());

describe("인증 API", () => {
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
