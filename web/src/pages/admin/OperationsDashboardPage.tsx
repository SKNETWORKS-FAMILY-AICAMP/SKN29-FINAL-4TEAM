import "../system/SystemPage.css";

export default function OperationsDashboardPage() {
  return (
    <main className="system-page">
      <section className="system-card">
        <small>ADMIN-01 · PLACEHOLDER</small>
        <h1>운영 대시보드</h1>
        <p>
          운영 API와 역할별 집계 계약이 확정되면 지연·오류·근거 부족 문의를
          연결합니다. 현재는 Route·권한·정보 구조만 검증합니다.
        </p>
        <div className="system-card__plan" aria-label="운영 대시보드 설계 범위">
          <h2>확정 전 정보 구조</h2>
          <dl>
            <div>
              <dt>지표</dt>
              <dd>처리 지연 · 오류 · 근거 부족 · 위험 문의</dd>
            </div>
            <div>
              <dt>필터</dt>
              <dd>기간 · 상태 · 위험도 · 담당 역할 · 제품 모델</dd>
            </div>
            <div>
              <dt>연동</dt>
              <dd>운영 집계 API 계약 확정 후 실제 수치 표시</dd>
            </div>
          </dl>
          <small>현재 화면에는 임의 운영 수치를 표시하지 않습니다.</small>
        </div>
      </section>
    </main>
  );
}
