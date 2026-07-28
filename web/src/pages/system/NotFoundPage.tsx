import { useNavigate } from "react-router-dom";

import EmptyState from "../../common/components/feedback/EmptyState";
import "./SystemPage.css";

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <main className="system-page">
      <EmptyState
        title="페이지를 찾을 수 없습니다."
        description="주소가 올바른지 확인하거나 업무 홈으로 돌아가 주세요."
        actionLabel="업무 홈으로 이동"
        onAction={() => navigate("/", { replace: true })}
      />
    </main>
  );
}
