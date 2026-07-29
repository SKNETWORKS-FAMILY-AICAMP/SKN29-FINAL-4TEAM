import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth, type AppRole } from "../../app/providers/authContext";
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
  const { isAuthenticated, signInAs, user } = useAuth();
  const [role, setRole] = useState<AppRole>("CONSULTANT");

  if (isAuthenticated && user) {
    return <Navigate to={getRoleHome(user.roleCode)} replace />;
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    signInAs(role);
    navigate(getSafeReturnTo(location.state, role), { replace: true });
  };

  return (
    <main className="system-page">
      <section className="system-card" aria-labelledby="login-title">
        <small>DEMO AUTH · MOCK</small>
        <h1 id="login-title">워터케어 ONE 로그인</h1>
        <p>
          실제 인증 API 연결 전 사용하는 합성 계정 로그인입니다. 실제 비밀번호와
          개인정보를 입력하지 마세요.
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
          <button type="submit">Mock 계정으로 로그인</button>
        </form>
      </section>
    </main>
  );
}
