import { useNavigate } from "react-router-dom";

import { useAuth } from "../../../app/providers/authContext";
import { ROUTE_PATHS } from "../../../app/router/routePaths";
import { getConsultantDisplayName } from "../model/consultantDisplayName";
import "./ConsultantUserMenu.css";

interface ConsultantUserMenuProps {
  className?: string;
}

export default function ConsultantUserMenu({
  className = "",
}: ConsultantUserMenuProps) {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const displayName = getConsultantDisplayName(user?.displayName);
  const employeeNumber = "2026-001-256";

  const handleSignOut = async () => {
    await signOut();
    navigate(ROUTE_PATHS.login, { replace: true });
  };

  return (
    <div
      className={`consultant-user-menu ${className}`.trim()}
      data-e2e-sensitive="true"
    >
      <strong className="consultant-user-menu__name">{displayName}</strong>
      <i className="consultant-user-menu__divider" aria-hidden="true" />
      <small className="consultant-user-menu__employee-number">
        <span className="consultant-visually-hidden">사번 </span>
        {employeeNumber}
      </small>
      <i className="consultant-user-menu__divider" aria-hidden="true" />
      <button
        type="button"
        className="consultant-user-menu__sign-out"
        onClick={() => void handleSignOut()}
      >
        로그아웃
      </button>
    </div>
  );
}
