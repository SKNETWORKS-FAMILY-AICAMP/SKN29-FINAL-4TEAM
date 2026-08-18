import { useNavigate } from "react-router-dom";

import { useAuth } from "../../../app/providers/authContext";
import { ROUTE_PATHS } from "../../../app/router/routePaths";
import "./ConsultantUserMenu.css";

interface ConsultantUserMenuProps {
  className?: string;
}

function getConsultantDisplayName(displayName?: string) {
  return displayName === "합성 상담사 001"
    ? "한예나"
    : (displayName ?? "상담사");
}

function getConsultantEmployeeNumber(
  userId?: string,
  displayName?: string,
) {
  return displayName === "합성 상담사 001" ? "001" : (userId ?? "-");
}

export default function ConsultantUserMenu({
  className = "",
}: ConsultantUserMenuProps) {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const displayName = getConsultantDisplayName(user?.displayName);
  const employeeNumber = getConsultantEmployeeNumber(
    user?.id,
    user?.displayName,
  );

  const handleSignOut = async () => {
    await signOut();
    navigate(ROUTE_PATHS.login, { replace: true });
  };

  return (
    <div className={`consultant-user-menu ${className}`.trim()}>
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
