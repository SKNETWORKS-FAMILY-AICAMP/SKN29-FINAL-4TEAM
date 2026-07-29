import type {
  AppRole,
  AuthenticatedUser,
} from "../../../app/providers/authContext";
import type { AuthSession } from "./authSession";

export interface AuthenticatedUserDto {
  id: string;
  display_name: string;
  role_code: AppRole;
  is_active: boolean;
  customer_profile: Record<string, unknown> | null;
  allowed_actions: readonly string[];
}

export interface LoginResponseDto {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  access_expires_in: number;
  refresh_expires_in: number;
  user: AuthenticatedUserDto;
}

export function mapAuthenticatedUser(
  dto: AuthenticatedUserDto,
): AuthenticatedUser {
  return {
    id: dto.id,
    displayName: dto.display_name,
    roleCode: dto.role_code,
    isActive: dto.is_active,
  };
}

export function mapLoginResponse(dto: LoginResponseDto): AuthSession {
  return {
    accessToken: dto.access_token,
    refreshToken: dto.refresh_token,
    accessExpiresIn: dto.access_expires_in,
    refreshExpiresIn: dto.refresh_expires_in,
    user: mapAuthenticatedUser(dto.user),
  };
}
