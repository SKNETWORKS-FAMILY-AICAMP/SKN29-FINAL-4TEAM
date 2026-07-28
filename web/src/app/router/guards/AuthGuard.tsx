import { Navigate, Outlet, useLocation } from "react-router-dom";

import LoadingState from "../../../common/components/feedback/LoadingState";
import { useAuth } from "../../providers/authContext";
import { ROUTE_PATHS } from "../routePaths";

export default function AuthGuard() {
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingState title="로그인 상태를 확인하고 있습니다." />;
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={ROUTE_PATHS.login}
        replace
        state={{ returnTo: `${location.pathname}${location.search}` }}
      />
    );
  }

  return <Outlet />;
}
