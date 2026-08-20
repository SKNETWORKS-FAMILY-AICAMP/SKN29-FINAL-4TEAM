import EmptyState from "../../common/components/feedback/EmptyState";

export default function OperationsInfographicPage() {
  return (
    <main className="operations-main operations-insights-page">
      <header className="operations-page-head operations-insights-head">
        <div>
          <small>ADMIN-02 · API PENDING</small>
          <h1>운영 인포그래픽</h1>
          <p>운영 집계 API가 제공되면 핵심 운영 수치와 분포를 표시합니다.</p>
        </div>
        <span>운영 집계 API 연동 대기</span>
      </header>

      <section
        className="operations-panel operations-feedback"
        aria-label="운영 인포그래픽 연동 상태"
      >
        <EmptyState
          title="운영 인포그래픽 API 연동을 기다리고 있습니다."
          description="현재는 로컬 합성 데이터로 운영 지표나 분포를 계산하지 않습니다. Backend 집계 API가 제공되면 이 화면에 표시합니다."
        />
      </section>
    </main>
  );
}
