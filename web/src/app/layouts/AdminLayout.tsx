import { NavLink, Outlet, useNavigate } from "react-router-dom";

import ApiRuntimeStatus from "../../features/runtime-status/components/ApiRuntimeStatus";
import "../../pages/admin/OperationsDashboardPage.css";
import "../../pages/admin/OperationsDashboardTheme.css";
import "../../common/styles/water-glass-theme.css";
import "../../common/styles/waterdrop-workspaces.css";
import "../../common/styles/readable-dashboard-theme.css";
import { useAuth } from "../providers/authContext";
import { ROUTE_PATHS } from "../router/routePaths";

export default function AdminLayout() {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();

  const handleSignOut = async () => {
    await signOut();
    navigate(ROUTE_PATHS.login, { replace: true });
  };

  return (
    <div className="operations-page waterdrop-workspace waterdrop-workspace--operator">
      <header className="operations-topbar">
        <div className="operations-brand">
          <span>W</span>
          <div>
            <strong>Water Bridge</strong>
            <small>정수기 고객 케어 운영</small>
          </div>
        </div>
        <nav className="operations-navigation" aria-label="운영자 화면 바로가기">
          <NavLink
            to={ROUTE_PATHS.adminDashboard}
            end
            className={({ isActive }) => (isActive ? "is-active" : undefined)}
          >
            <span aria-hidden="true">01</span>
            운영 대시보드
          </NavLink>
          <NavLink
            to={ROUTE_PATHS.adminInsights}
            className={({ isActive }) => (isActive ? "is-active" : undefined)}
          >
            <span aria-hidden="true">02</span>
            인포그래픽
          </NavLink>
        </nav>
        <ApiRuntimeStatus className="operations-runtime-status" compact />
        <div className="operations-user">
          <div>
            <strong>{user?.displayName ?? "운영 담당자"}</strong>
            <small>OPERATOR · 합성 Mock</small>
          </div>
          <button type="button" onClick={() => void handleSignOut()}>
            로그아웃
          </button>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
