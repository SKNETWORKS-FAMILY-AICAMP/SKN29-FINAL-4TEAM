import { describe, expect, it } from "vitest";

import { mapLoginResponse } from "../../src/features/auth/model/authContract";

describe("인증 계약 Mapper", () => {
  it("로그인 응답의 Access·Refresh Token과 사용자를 메모리 세션으로 변환한다", () => {
    const session = mapLoginResponse({
      access_token: "access-token",
      refresh_token: "refresh-token",
      token_type: "Bearer",
      access_expires_in: 3600,
      refresh_expires_in: 604800,
      user: {
        id: "00000000-0000-4000-8000-000000000102",
        display_name: "한유진",
        role_code: "CONSULTANT",
        is_active: true,
        customer_profile: null,
        allowed_actions: [],
      },
    });

    expect(session).toEqual({
      accessToken: "access-token",
      refreshToken: "refresh-token",
      accessExpiresIn: 3600,
      refreshExpiresIn: 604800,
      user: {
        id: "00000000-0000-4000-8000-000000000102",
        displayName: "한유진",
        roleCode: "CONSULTANT",
        isActive: true,
      },
    });
  });
});
