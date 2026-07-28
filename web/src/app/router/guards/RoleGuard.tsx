import { Navigate, Outlet } from "react-router-dom";

import { useAuth, type AppRole } from "../../providers/authContext";
import { ROUTE_PATHS } from "../routePaths";

export default function RoleGuard({
  allowedRoles,
}: {
  allowedRoles: readonly AppRole[];
}) {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to={ROUTE_PATHS.login} replace />;
  }

  if (!allowedRoles.includes(user.roleCode)) {
    return <Navigate to={ROUTE_PATHS.forbidden} replace />;
  }

  return <Outlet />;
}
