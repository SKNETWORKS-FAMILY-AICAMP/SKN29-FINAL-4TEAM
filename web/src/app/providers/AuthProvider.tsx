import { useMemo, useState, type ReactNode } from "react";

import { appEnv } from "../config/env";
import {
  AuthContext,
  type AppRole,
  type AuthenticatedUser,
  type AuthContextValue,
} from "./authContext";

interface AuthProviderProps {
  children: ReactNode;
  initialUser?: AuthenticatedUser | null;
}

const MOCK_USERS: Record<AppRole, AuthenticatedUser> = {
  CUSTOMER: {
    id: "DEMO-CUSTOMER-01",
    displayName: "합성 고객",
    roleCode: "CUSTOMER",
    isActive: true,
  },
  CONSULTANT: {
    id: "STAFF-CONS-01",
    displayName: "한유진",
    roleCode: "CONSULTANT",
    isActive: true,
  },
  TECHNICIAN: {
    id: "STAFF-TECH-01",
    displayName: "합성 기사",
    roleCode: "TECHNICIAN",
    isActive: true,
  },
  OPERATOR: {
    id: "STAFF-OPS-01",
    displayName: "합성 운영자",
    roleCode: "OPERATOR",
    isActive: true,
  },
};

function getDefaultMockUser() {
  if (!appEnv.useMockApi || !appEnv.mockAuthenticated) return null;
  return MOCK_USERS[appEnv.mockRole];
}

export function AuthProvider({ children, initialUser }: AuthProviderProps) {
  const [user, setUser] = useState<AuthenticatedUser | null>(() =>
    initialUser === undefined ? getDefaultMockUser() : initialUser,
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: Boolean(user?.isActive),
      isLoading: false,
      signInAs: (role) => setUser(MOCK_USERS[role]),
      signOut: () => setUser(null),
    }),
    [user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
