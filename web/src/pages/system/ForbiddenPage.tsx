import { useNavigate } from "react-router-dom";

import { useAuth } from "../../app/providers/authContext";
import { ROUTE_PATHS } from "../../app/router/routePaths";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import "./SystemPage.css";

export default function ForbiddenPage() {
  const navigate = useNavigate();
  const { signOut, user } = useAuth();

  const handleAction = async () => {
    if (user?.roleCode === "CONSULTANT") {
      navigate(ROUTE_PATHS.consultantInquiryList, { replace: true });
      return;
    }
    if (user?.roleCode === "OPERATOR") {
      navigate(ROUTE_PATHS.adminDashboard, { replace: true });
      return;
    }
    await signOut();
    navigate(ROUTE_PATHS.login, { replace: true });
  };

  return (
    <main className="system-page">
      <ForbiddenState
        title="이 역할로 접근할 수 없는 화면입니다."
        description="로그인한 역할의 업무 범위와 요청한 화면이 일치하지 않습니다."
        actionLabel={user ? "내 업무 화면으로 이동" : "로그인으로 이동"}
        onAction={handleAction}
      />
    </main>
  );
}
