import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth, type AppRole } from "../../app/providers/authContext";
import { appEnv } from "../../app/config/env";
import { ROUTE_PATHS } from "../../app/router/routePaths";
import "../system/SystemPage.css";

const STAFF_ROLES: readonly { code: AppRole; label: string }[] = [
  { code: "CONSULTANT", label: "상담사" },
  { code: "OPERATOR", label: "운영 담당자" },
  { code: "TECHNICIAN", label: "방문 기사" },
  { code: "CUSTOMER", label: "고객" },
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
  const { isAuthenticated, isLoading, signInAs, user } = useAuth();
  const [role, setRole] = useState<AppRole>("CONSULTANT");
  const [loginError, setLoginError] = useState<string | null>(null);

  if (isAuthenticated && user) {
    return <Navigate to={getRoleHome(user.roleCode)} replace />;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoginError(null);
    try {
      await signInAs(role);
      navigate(getSafeReturnTo(location.state, role), { replace: true });
    } catch {
      setLoginError("로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.");
    }
  };

  return (
    <main className="system-page">
      <section className="system-card" aria-labelledby="login-title">
        <small>DEMO AUTH · {appEnv.useMockApi ? "MOCK" : "API"}</small>
        <h1 id="login-title">워터케어 ONE 로그인</h1>
        <p>
          {appEnv.useMockApi
            ? "인증 API 연결 전 사용하는 합성 계정 로그인입니다. 실제 비밀번호와 개인정보를 입력하지 마세요."
            : "백엔드 데모 인증 API로 로그인합니다. 실제 비밀번호와 개인정보를 입력하지 마세요."}
        </p>
        <form onSubmit={handleSubmit}>
          <label>
            역할
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
          {loginError && <p role="alert">{loginError}</p>}
        </form>
      </section>
    </main>
  );
}
