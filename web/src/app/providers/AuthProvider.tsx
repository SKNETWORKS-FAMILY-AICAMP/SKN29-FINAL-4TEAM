import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { configureApiAuth } from "../../common/api/httpClient";
import { createCorrelationId } from "../../common/api/requestContext";
import {
  DEMO_USER_CODES,
  loginWithDemoCode,
  refreshAuthSession,
  revokeRefreshToken,
} from "../../features/auth/api/authApi";
import {
  authSessionStore,
  type AuthSession,
} from "../../features/auth/model/authSession";
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
    id: "00000000-0000-4000-8000-000000000101",
    displayName: "합성 고객",
    roleCode: "CUSTOMER",
    isActive: true,
  },
  CONSULTANT: {
    id: "00000000-0000-4000-8000-000000000102",
    displayName: "한유진",
    roleCode: "CONSULTANT",
    isActive: true,
  },
  TECHNICIAN: {
    id: "00000000-0000-4000-8000-000000000103",
    displayName: "합성 기사",
    roleCode: "TECHNICIAN",
    isActive: true,
  },
  OPERATOR: {
    id: "00000000-0000-4000-8000-000000000104",
    displayName: "합성 운영자",
    roleCode: "OPERATOR",
    isActive: true,
  },
};

function getDefaultMockUser() {
  if (!appEnv.useMockApi || !appEnv.mockAuthenticated) return null;
  return MOCK_USERS[appEnv.mockRole];
}

function createMockSession(user: AuthenticatedUser): AuthSession {
  return {
    accessToken: `mock-access-${user.roleCode}-${createCorrelationId()}`,
    refreshToken: `mock-refresh-${user.roleCode}-${createCorrelationId()}`,
    accessExpiresIn: 3600,
    refreshExpiresIn: 604800,
    user,
  };
}

export function AuthProvider({ children, initialUser }: AuthProviderProps) {
  const [user, setUser] = useState<AuthenticatedUser | null>(() =>
    initialUser === undefined ? getDefaultMockUser() : initialUser,
  );
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!appEnv.useMockApi) return;

    if (!user) {
      authSessionStore.clear();
      return;
    }

    if (authSessionStore.getSession()?.user.id !== user.id) {
      authSessionStore.setSession(createMockSession(user));
    }
  }, [user]);

  useEffect(() => {
    configureApiAuth({
      getAccessToken: () => authSessionStore.getAccessToken(),
      refreshAccessToken: async () => {
        const currentSession = authSessionStore.getSession();
        if (!currentSession) return null;

        const nextSession = appEnv.useMockApi
          ? createMockSession(currentSession.user)
          : await refreshAuthSession(currentSession.refreshToken);
        authSessionStore.setSession(nextSession);
        setUser(nextSession.user);
        return nextSession.accessToken;
      },
      clearSession: () => {
        authSessionStore.clear();
        setUser(null);
      },
    });

    return () => configureApiAuth(null);
  }, []);

  const signInAs = useCallback(async (role: AppRole) => {
    setIsLoading(true);
    try {
      const session = appEnv.useMockApi
        ? createMockSession(MOCK_USERS[role])
        : await loginWithDemoCode(DEMO_USER_CODES[role]);
      authSessionStore.setSession(session);
      setUser(session.user);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const signOut = useCallback(async () => {
    const refreshToken = authSessionStore.getSession()?.refreshToken;
    try {
      if (!appEnv.useMockApi && refreshToken) {
        await revokeRefreshToken(refreshToken);
      }
    } finally {
      authSessionStore.clear();
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: Boolean(user?.isActive),
      isLoading,
      signInAs,
      signOut,
    }),
    [isLoading, signInAs, signOut, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
