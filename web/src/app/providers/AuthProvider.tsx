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
  getCurrentUser,
  loginWithDemoCode,
  loginWithPassword,
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

// 화면 데이터 소스와 미리보기 인증을 분리한다. 디자인 모드에서도 배포용
// REMOTE 페이지를 사용하되 실제 계정/토큰은 필요하지 않다.
const useSyntheticAuth = appEnv.useMockApi || appEnv.isDesignPreview;

const MOCK_USERS: Record<AppRole, AuthenticatedUser> = {
  CUSTOMER: {
    id: "00000000-0000-4000-8000-000000000101",
    displayName: "합성 고객",
    roleCode: "CUSTOMER",
    isActive: true,
  },
  CONSULTANT: {
    id: "00000000-0000-4000-8000-000000000102",
    displayName: appEnv.isDesignPreview ? "미리보기 상담사" : "합성 상담사 001",
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
  if (!useSyntheticAuth || !appEnv.mockAuthenticated) return null;
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

function getInitialUser(
  initialUser: AuthenticatedUser | null | undefined,
): AuthenticatedUser | null {
  if (initialUser !== undefined) return initialUser;
  const storedUser = authSessionStore.getSession()?.user;
  if (useSyntheticAuth && storedUser) {
    return MOCK_USERS[storedUser.roleCode];
  }
  return storedUser ?? getDefaultMockUser();
}

function shouldHydrateStoredRemoteSession(
  initialUser: AuthenticatedUser | null | undefined,
): boolean {
  return (
    initialUser === undefined &&
    !useSyntheticAuth &&
    authSessionStore.getSession() !== null
  );
}

async function hydrateRemoteSessionUser(): Promise<AuthSession> {
  const currentUser = await getCurrentUser();
  const currentSession = authSessionStore.getSession();
  if (!currentSession) {
    throw new Error("현재 사용자 정보를 반영할 인증 세션이 없습니다.");
  }

  const hydratedSession = { ...currentSession, user: currentUser };
  authSessionStore.setSession(hydratedSession);
  return hydratedSession;
}

export function AuthProvider({ children, initialUser }: AuthProviderProps) {
  const [user, setUser] = useState<AuthenticatedUser | null>(() =>
    getInitialUser(initialUser),
  );
  const [isLoading, setIsLoading] = useState(() =>
    shouldHydrateStoredRemoteSession(initialUser),
  );

  useEffect(() => {
    if (!useSyntheticAuth) return;

    if (!user) {
      authSessionStore.clear();
      return;
    }

    const storedUser = authSessionStore.getSession()?.user;
    if (
      storedUser?.id !== user.id ||
      storedUser.displayName !== user.displayName ||
      storedUser.roleCode !== user.roleCode
    ) {
      authSessionStore.setSession(createMockSession(user));
    }
  }, [user]);

  useEffect(() => {
    configureApiAuth({
      getAccessToken: () => authSessionStore.getAccessToken(),
      refreshAccessToken: async () => {
        const currentSession = authSessionStore.getSession();
        if (!currentSession) return null;

        const refreshedSession = useSyntheticAuth
          ? createMockSession(currentSession.user)
          : await refreshAuthSession(currentSession.refreshToken);
        const nextSession = useSyntheticAuth
          ? refreshedSession
          : { ...refreshedSession, user: currentSession.user };
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

  useEffect(() => {
    if (useSyntheticAuth || initialUser !== undefined) return;
    if (!authSessionStore.getSession()) return;

    let isActive = true;
    void hydrateRemoteSessionUser()
      .then((session) => {
        if (isActive) setUser(session.user);
      })
      .catch(() => {
        if (!isActive) return;
        authSessionStore.clear();
        setUser(null);
      })
      .finally(() => {
        if (isActive) setIsLoading(false);
      });

    return () => {
      isActive = false;
    };
  }, [initialUser]);

  const signInAs = useCallback(async (role: AppRole) => {
    setIsLoading(true);
    try {
      const session = useSyntheticAuth
        ? createMockSession(MOCK_USERS[role])
        : await loginWithDemoCode(DEMO_USER_CODES[role]);
      authSessionStore.setSession(session);
      if (useSyntheticAuth) {
        setUser(session.user);
      } else {
        try {
          const hydratedSession = await hydrateRemoteSessionUser();
          setUser(hydratedSession.user);
        } catch (error) {
          authSessionStore.clear();
          setUser(null);
          throw error;
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const signInWithPassword = useCallback(
    async (username: string, password: string) => {
      if (useSyntheticAuth) {
        throw new Error("ID/PW 로그인은 Backend 연결 모드에서만 사용할 수 있습니다.");
      }
      setIsLoading(true);
      try {
        const session = await loginWithPassword(username, password);
        authSessionStore.setSession(session);
        try {
          const hydratedSession = await hydrateRemoteSessionUser();
          setUser(hydratedSession.user);
          return hydratedSession.user;
        } catch (error) {
          authSessionStore.clear();
          setUser(null);
          throw error;
        }
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const signOut = useCallback(async () => {
    const refreshToken = authSessionStore.getSession()?.refreshToken;
    try {
      if (!useSyntheticAuth && refreshToken) {
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
      signInWithPassword,
      signOut,
    }),
    [isLoading, signInAs, signInWithPassword, signOut, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
