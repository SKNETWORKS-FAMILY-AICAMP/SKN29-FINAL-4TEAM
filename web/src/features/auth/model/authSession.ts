import type { AuthenticatedUser } from "../../../app/providers/authContext";

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  accessExpiresIn: number;
  refreshExpiresIn: number;
  user: AuthenticatedUser;
}

class InMemoryAuthSessionStore {
  private session: AuthSession | null = null;

  getSession(): AuthSession | null {
    return this.session;
  }

  getAccessToken(): string | null {
    return this.session?.accessToken ?? null;
  }

  setSession(session: AuthSession): void {
    this.session = session;
  }

  clear(): void {
    this.session = null;
  }
}

export const authSessionStore = new InMemoryAuthSessionStore();
