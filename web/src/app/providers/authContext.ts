import { createContext, useContext } from "react";

export type AppRole = "CUSTOMER" | "CONSULTANT" | "TECHNICIAN" | "OPERATOR";

export interface AuthenticatedUser {
  id: string;
  displayName: string;
  roleCode: AppRole;
  isActive: boolean;
}

export interface AuthContextValue {
  user: AuthenticatedUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signInAs: (role: AppRole) => Promise<void>;
  signInWithPassword: (
    username: string,
    password: string,
  ) => Promise<AuthenticatedUser>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth는 AuthProvider 안에서 사용해야 합니다.");
  }
  return value;
}
