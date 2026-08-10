import { useMemo } from "react";

import OperationsDistributionChart from "../../features/operations-dashboard/components/OperationsDistributionChart";
import OperationsMetricCards from "../../features/operations-dashboard/components/OperationsMetricCards";
import {
  createOperationsDashboardSummary,
  DEFAULT_OPERATIONS_FILTERS,
} from "../../features/operations-dashboard/model/operationsDashboardModel";
import { consultantWorkspaceRepository } from "../../features/consultation/repositories/consultantWorkspaceRepository";

const OPERATIONS_INQUIRIES = consultantWorkspaceRepository.listAllInquiries();

export default function OperationsInfographicPage() {
  const summary = useMemo(
    () =>
      createOperationsDashboardSummary(
        OPERATIONS_INQUIRIES,
        DEFAULT_OPERATIONS_FILTERS,
      ),
    [],
  );

  return (
    <main className="operations-main operations-insights-page">
      <header className="operations-page-head operations-insights-head">
        <div>
          <small>ADMIN-02 · INFOGRAPHIC</small>
          <h1>운영 인포그래픽</h1>
          <p>필터와 문의 목록 없이 핵심 운영 수치와 분포만 한눈에 확인합니다.</p>
        </div>
        <span>기준 데이터 · 공식 합성 문의 {OPERATIONS_INQUIRIES.length}건</span>
      </header>

      <section className="operations-insights-intro" aria-label="인포그래픽 안내">
        <div>
          <small>AT A GLANCE</small>
          <h2>고객 문의 운영 현황</h2>
        </div>
        <p>전체 문의를 기준으로 상담·방문·완료 흐름과 주요 증상 분포를 요약했습니다.</p>
      </section>

      <OperationsMetricCards metrics={summary.metrics} />
      <section className="operations-distributions operations-insights-grid" aria-label="운영 인포그래픽">
        <OperationsDistributionChart
          title="주요 증상 유형"
          description="전체 문의 기준"
          items={summary.symptomDistribution}
        />
        <OperationsDistributionChart
          title="문의 처리 상태"
          description="현재 상태 기준"
          items={summary.statusDistribution}
        />
      </section>
    </main>
  );
}
