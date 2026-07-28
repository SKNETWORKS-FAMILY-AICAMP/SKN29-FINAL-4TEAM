import { useNavigate } from "react-router-dom";

import ErrorState from "../../common/components/feedback/ErrorState";
import "./SystemPage.css";

export default function ErrorPage() {
  const navigate = useNavigate();
  return (
    <main className="system-page">
      <ErrorState
        title="화면을 처리하지 못했습니다."
        description="입력 내용이 있다면 보존 여부를 확인한 뒤 업무 화면으로 돌아가 주세요."
        retryLabel="업무 홈으로 이동"
        onRetry={() => navigate("/", { replace: true })}
      />
    </main>
  );
}
