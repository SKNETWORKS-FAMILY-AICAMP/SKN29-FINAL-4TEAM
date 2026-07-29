import { requestApi } from "../../../common/api/httpClient";
import type { AppRole } from "../../../app/providers/authContext";
import {
  mapAuthenticatedUser,
  mapLoginResponse,
  type AuthenticatedUserDto,
  type LoginResponseDto,
} from "../model/authContract";
import type { AuthSession } from "../model/authSession";
import type { AuthenticatedUser } from "../../../app/providers/authContext";

export const DEMO_USER_CODES: Record<AppRole, string> = {
  CUSTOMER: "DEMO-CUSTOMER-001",
  CONSULTANT: "DEMO-CONSULTANT-001",
  TECHNICIAN: "DEMO-TECHNICIAN-001",
  OPERATOR: "DEMO-OPERATOR-001",
};

export async function loginWithDemoCode(
  demoUserCode: string,
): Promise<AuthSession> {
  const response = await requestApi<LoginResponseDto>("/auth/demo-login", {
    method: "POST",
    auth: "none",
    body: { demo_user_code: demoUserCode },
  });
  if (!response.data) {
    throw new Error("로그인 응답에 세션 정보가 없습니다.");
  }
  return mapLoginResponse(response.data);
}

export async function refreshAuthSession(
  refreshToken: string,
): Promise<AuthSession> {
  const response = await requestApi<LoginResponseDto>("/auth/refresh", {
    method: "POST",
    auth: "none",
    body: { refresh_token: refreshToken },
  });
  if (!response.data) {
    throw new Error("토큰 갱신 응답에 세션 정보가 없습니다.");
  }
  return mapLoginResponse(response.data);
}

export async function revokeRefreshToken(refreshToken: string): Promise<void> {
  await requestApi<{ revoked: true }>("/auth/logout", {
    method: "POST",
    auth: "none",
    body: { refresh_token: refreshToken },
  });
}

export async function getCurrentUser(): Promise<AuthenticatedUser> {
  const response = await requestApi<AuthenticatedUserDto>("/me");
  if (!response.data) {
    throw new Error("현재 사용자 응답이 없습니다.");
  }
  return mapAuthenticatedUser(response.data);
}
