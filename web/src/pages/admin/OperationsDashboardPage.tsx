import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ROUTE_PATHS } from "../../app/router/routePaths";
import { useAuth } from "../../app/providers/authContext";
import RiskBadge from "../../common/components/badge/RiskBadge";
import StatusBadge from "../../common/components/badge/StatusBadge";
import DataTable, {
  type DataTableColumn,
} from "../../common/components/data-display/DataTable";
import ErrorState from "../../common/components/feedback/ErrorState";
import LoadingState from "../../common/components/feedback/LoadingState";
import OperationsDashboardFilters from "../../features/operations-dashboard/components/OperationsDashboardFilters";
import OperationsDistributionChart from "../../features/operations-dashboard/components/OperationsDistributionChart";
import OperationsExceptionTable from "../../features/operations-dashboard/components/OperationsExceptionTable";
import OperationsMetricCards from "../../features/operations-dashboard/components/OperationsMetricCards";
import useOperationsDashboardFilters from "../../features/operations-dashboard/hooks/useOperationsDashboardFilters";
import {
  createOperationsDashboardSummary,
  getOperationsFilterOptions,
} from "../../features/operations-dashboard/model/operationsDashboardModel";
import {
  formatWorkspaceDateTime,
  getStatusBadgeVariant,
  STATUS_LABELS,
} from "../../features/consultation/model/consultantWorkspaceModel";
import type { CounselorInquiry } from "../../features/consultation/model/consultantWorkspaceTypes";
import { consultantWorkspaceRepository } from "../../features/consultation/repositories/consultantWorkspaceRepository";
import ApiIntegrationPanel from "../../features/runtime-status/components/ApiIntegrationPanel";
import ApiRuntimeStatus from "../../features/runtime-status/components/ApiRuntimeStatus";
import "./OperationsDashboardPage.css";
import "./OperationsDashboardTheme.css";

const OPERATIONS_INQUIRIES =
  consultantWorkspaceRepository.listAllInquiries();

const INQUIRY_COLUMNS: readonly DataTableColumn<CounselorInquiry>[] = [
  {
    key: "inquiry",
    header: "문의",
    render: (item) => (
      <span className="operations-table__primary">
        <b>{item.inquiryCode}</b>
        <small>{item.symptomLabel}</small>
      </span>
    ),
  },
  {
    key: "risk",
    header: "위험도",
    render: (item) => <RiskBadge level={item.riskLevel.toLowerCase()} size="compact" />,
  },
  {
    key: "status",
    header: "상태",
    render: (item) => (
      <StatusBadge
        label={STATUS_LABELS[item.status]}
        size="compact"
        variant={getStatusBadgeVariant(item.status)}
      />
    ),
  },
  { key: "assignee", header: "처리 담당", render: (item) => item.assignedCounselor },
  { key: "model", header: "제품 모델", render: (item) => item.productCode },
  {
    key: "updatedAt",
    header: "마지막 변경",
    render: (item) => (
      <time dateTime={item.updatedAt}>{formatWorkspaceDateTime(item.updatedAt)}</time>
    ),
  },
];

export default function OperationsDashboardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, signOut } = useAuth();
  const { filters, hasChangedFilters, resetFilters, setFilters } =
    useOperationsDashboardFilters();
  const mockState = searchParams.get("mockState");
  const sourceInquiries = useMemo(
    () => (mockState === "empty" ? [] : OPERATIONS_INQUIRIES),
    [mockState],
  );
  const options = useMemo(
    () => getOperationsFilterOptions(OPERATIONS_INQUIRIES),
    [],
  );
  const summary = useMemo(
    () => createOperationsDashboardSummary(sourceInquiries, filters),
    [filters, sourceInquiries],
  );

  const handleSignOut = async () => {
    await signOut();
    navigate(ROUTE_PATHS.login, { replace: true });
  };

  const renderContent = () => {
    if (mockState === "loading") {
      return (
        <div className="operations-panel operations-feedback">
          <LoadingState
            title="운영 현황을 집계하고 있습니다."
            description="합성 문의의 상태·전환·예외 정보를 확인하고 있습니다."
          />
        </div>
      );
    }
    if (mockState === "error") {
      return (
        <div className="operations-panel operations-feedback">
          <ErrorState
            title="운영 현황을 불러오지 못했습니다."
            description="현재 조회 조건은 유지됩니다. 잠시 후 다시 시도해 주세요."
            onRetry={() => navigate(ROUTE_PATHS.adminDashboard, { replace: true })}
          />
        </div>
      );
    }

    return (
      <>
        <OperationsMetricCards metrics={summary.metrics} />
        <section className="operations-distributions" aria-label="운영 분포 지표">
          <OperationsDistributionChart
            title="주요 증상 유형"
            description="조회 문의 기준"
            items={summary.symptomDistribution}
          />
          <OperationsDistributionChart
            title="문의 처리 상태"
            description="현재 상태 기준"
            items={summary.statusDistribution}
          />
        </section>
        <OperationsExceptionTable exceptions={summary.exceptions} />
        <section className="operations-panel operations-table-section">
          <div className="operations-section-head">
            <div>
              <small>INQUIRY</small>
              <h2>조건별 문의 현황</h2>
            </div>
            <strong>{summary.inquiries.length}건</strong>
          </div>
          <DataTable
            caption="운영 조회 조건에 포함된 문의"
            columns={INQUIRY_COLUMNS}
            emptyMessage="현재 조회 조건에 맞는 문의가 없습니다."
            getRowKey={(item) => item.inquiryId}
            rows={summary.inquiries}
          />
        </section>
      </>
    );
  };

  return (
    <div className="operations-page">
      <header className="operations-topbar">
        <div className="operations-brand">
          <span>W</span>
          <div>
            <strong>워터케어 ONE</strong>
            <small>정수기 고객 케어 운영</small>
          </div>
        </div>
        <nav className="operations-navigation" aria-label="운영자 화면 바로가기">
          <a href="#operations-overview">
            <span aria-hidden="true">01</span>
            운영 개요
          </a>
          <a href="#operations-filters">
            <span aria-hidden="true">02</span>
            조회 조건
          </a>
          <a href="#operations-results">
            <span aria-hidden="true">03</span>
            문의 현황
          </a>
        </nav>
        <ApiRuntimeStatus className="operations-runtime-status" compact />
        <div className="operations-user">
          <div>
            <strong>{user?.displayName ?? "운영 담당자"}</strong>
            <small>OPERATOR · 합성 Mock</small>
          </div>
          <button type="button" onClick={() => void handleSignOut()}>
            로그아웃
          </button>
        </div>
      </header>

      <main className="operations-main">
        <header id="operations-overview" className="operations-page-head">
          <div>
            <small>ADMIN-01 · P1 MOCK</small>
            <h1>운영 대시보드</h1>
            <p>문의 현황과 상담·방문 전환, 처리 예외를 공식 합성 데이터로 점검합니다.</p>
          </div>
          <span>기준 데이터 · 공식 합성 문의 {OPERATIONS_INQUIRIES.length}건</span>
        </header>

        <ApiIntegrationPanel />

        <div id="operations-filters">
          <OperationsDashboardFilters
            filters={filters}
            hasChangedFilters={hasChangedFilters}
            options={options}
            resultCount={summary.inquiries.length}
            onChange={setFilters}
            onReset={resetFilters}
          />
        </div>
        <div id="operations-results">{renderContent()}</div>
      </main>
    </div>
  );
}
