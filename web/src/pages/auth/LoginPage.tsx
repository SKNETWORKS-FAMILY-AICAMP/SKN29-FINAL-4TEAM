import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth, type AppRole } from "../../app/providers/authContext";
import { appEnv } from "../../app/config/env";
import { ROUTE_PATHS } from "../../app/router/routePaths";
import "../system/SystemPage.css";
import "./LoginPage.css";

const STAFF_ROLES: readonly { code: AppRole; label: string }[] = [
  { code: "CONSULTANT", label: "상담사" },
];

function getRoleHome(role: AppRole) {
  if (role === "CONSULTANT") return ROUTE_PATHS.consultantInquiryList;
  if (role === "OPERATOR") return ROUTE_PATHS.adminDashboard;
  return ROUTE_PATHS.forbidden;
}

function getSafeReturnTo(state: unknown, role: AppRole) {
  if (
    typeof state === "object" &&
    state !== null &&
    "returnTo" in state &&
    typeof state.returnTo === "string" &&
    state.returnTo.startsWith("/") &&
    !state.returnTo.startsWith("//")
  ) {
    return state.returnTo;
  }
  return getRoleHome(role);
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    isAuthenticated,
    isLoading,
    signInAs,
    signInWithPassword,
    user,
  } = useAuth();
  const [role, setRole] = useState<AppRole>("CONSULTANT");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);

  if (isAuthenticated && user) {
    return (
      <Navigate
        to={getSafeReturnTo(location.state, user.roleCode)}
        replace
      />
    );
  }

  const handleDemoSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoginError(null);
    try {
      await signInAs(role);
      navigate(getSafeReturnTo(location.state, role), { replace: true });
    } catch {
      setLoginError("로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    }
  };

  const handlePasswordSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoginError(null);
    try {
      const authenticatedUser = await signInWithPassword(username, password);
      setPassword("");
      navigate(getSafeReturnTo(location.state, authenticatedUser.roleCode), {
        replace: true,
      });
    } catch {
      setLoginError("사번 또는 비밀번호를 확인해 주세요.");
    }
  };

  return (
    <main className="system-page consultant-login-page">
      <section
        className="system-card consultant-login-card"
        aria-label="상담사 로그인"
      >
        <header className="consultant-login-card__brand">
          <span className="consultant-login-card__wordmark" aria-hidden="true">
            <span>Water</span>
            <span>Bridge</span>
          </span>
        </header>

        <div className="consultant-login-card__content">
          {!appEnv.useMockApi && (
            <form
              className="consultant-login-form"
              onSubmit={handlePasswordSubmit}
            >
              <label>
                사번
                <input
                  name="username"
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  required
                />
              </label>
              <label>
                비밀번호
                <input
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </label>
              <button type="submit" disabled={isLoading}>
                {isLoading ? "로그인 중…" : "사번/비밀번호로 로그인"}
              </button>
            </form>
          )}

          {!appEnv.useMockApi && (
            <div className="consultant-login-card__divider" aria-hidden="true">
              <span>테스트 계정</span>
            </div>
          )}

          <form
            className="consultant-login-form consultant-login-form--demo"
            onSubmit={handleDemoSubmit}
          >
            <label>
              테스트 역할
              <select
                value={role}
                onChange={(event) => setRole(event.target.value as AppRole)}
              >
                {STAFF_ROLES.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={isLoading}>
              {isLoading
                ? "로그인 중…"
                : appEnv.useMockApi
                  ? "Mock 계정으로 로그인"
                  : "API 데모 계정으로 로그인"}
            </button>
          </form>

          {loginError && (
            <p className="consultant-login-card__alert" role="alert">
              {loginError}
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
