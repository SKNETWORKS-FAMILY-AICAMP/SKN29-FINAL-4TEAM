import type { AuthenticatedUser } from "../../../app/providers/authContext";

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  accessExpiresIn: number;
  refreshExpiresIn: number;
  user: AuthenticatedUser;
}

const AUTH_SESSION_STORAGE_KEY = "waterbridge.auth.session.v1";

function isAuthSession(value: unknown): value is AuthSession {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<AuthSession>;
  return Boolean(
    typeof candidate.accessToken === "string" &&
      typeof candidate.refreshToken === "string" &&
      candidate.user &&
      typeof candidate.user.id === "string" &&
      typeof candidate.user.displayName === "string" &&
      typeof candidate.user.roleCode === "string" &&
      candidate.user.isActive,
  );
}

function getLocalStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage ?? null;
  } catch {
    return null;
  }
}

function readPersistedSession(): AuthSession | null {
  const storage = getLocalStorage();
  if (!storage) return null;
  try {
    const serialized = storage.getItem(AUTH_SESSION_STORAGE_KEY);
    if (!serialized) return null;
    const session: unknown = JSON.parse(serialized);
    if (isAuthSession(session)) return session;
    storage.removeItem(AUTH_SESSION_STORAGE_KEY);
  } catch {
    try {
      storage.removeItem(AUTH_SESSION_STORAGE_KEY);
    } catch {
      // Storage can be unavailable in privacy mode or non-browser test runners.
    }
  }
  return null;
}

class PersistentAuthSessionStore {
  private session: AuthSession | null = readPersistedSession();

  getSession(): AuthSession | null {
    return this.session;
  }

  getAccessToken(): string | null {
    return this.session?.accessToken ?? null;
  }

  setSession(session: AuthSession): void {
    this.session = session;
    const storage = getLocalStorage();
    if (storage) {
      storage.setItem(
        AUTH_SESSION_STORAGE_KEY,
        JSON.stringify(session),
      );
    }
  }

  clear(): void {
    this.session = null;
    getLocalStorage()?.removeItem(AUTH_SESSION_STORAGE_KEY);
  }
}

export const authSessionStore = new PersistentAuthSessionStore();
