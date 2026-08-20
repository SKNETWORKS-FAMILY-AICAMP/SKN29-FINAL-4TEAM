import EmptyState from "../../common/components/feedback/EmptyState";
import WaterDropBubbles from "../../common/components/water/WaterDropBubbles";
import ApiIntegrationPanel from "../../features/runtime-status/components/ApiIntegrationPanel";
import "./OperationsDashboardPage.css";
import "./OperationsDashboardTheme.css";
import "../../common/styles/water-glass-theme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";

export default function OperationsDashboardPage() {
  return (
    <main className="operations-main">
      <header id="operations-overview" className="operations-page-head waterdrop-hero">
        <WaterDropBubbles />
        <div className="operations-waterdrop-hero__copy">
          <span className="waterdrop-role-chip">운영 워크스페이스 · API 연동 대기</span>
          <small>ADMIN-01 · API PENDING</small>
          <h1>운영 대시보드</h1>
          <p>
            운영 관리자용 집계 API가 제공되면 문의 현황과 처리 흐름을 표시합니다.
          </p>
          <div className="operations-waterdrop-hero__facts" aria-label="운영 화면 안내">
            <span>운영 집계 미제공</span>
            <span>조회 필터 비활성</span>
            <span>로컬 계산값 미표시</span>
          </div>
        </div>
        <div className="operations-waterdrop-hero__visual" aria-label="운영 데이터 연동 상태">
          <span className="waterdrop-fixture-chip">운영 집계 API 미제공</span>
          <div className="operations-waterdrop-orb">
            <span>DATA STATUS</span>
            <strong aria-label="집계 데이터 없음">—</strong>
            <small>Backend 연동 대기</small>
          </div>
        </div>
      </header>

      <ApiIntegrationPanel />

      <section
        id="operations-results"
        className="operations-panel operations-feedback"
        aria-label="운영 집계 연동 상태"
      >
        <EmptyState
          title="운영 집계 API 연동을 기다리고 있습니다."
          description="운영 관리자 집계 API가 제공되기 전까지 지표, 분포, 예외 계산, 조회 필터와 문의 목록을 표시하지 않습니다."
        />
      </section>
    </main>
  );
}
