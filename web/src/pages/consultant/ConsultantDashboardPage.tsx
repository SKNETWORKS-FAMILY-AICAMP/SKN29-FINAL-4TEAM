import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  createInquiryDetailPath,
  createVisitTransitionPath,
} from "../../app/router/routePaths";
import { useAuth } from "../../app/providers/authContext";
import RiskBadge from "../../common/components/badge/RiskBadge";
import StatusBadge from "../../common/components/badge/StatusBadge";
import Pagination from "../../common/components/data-display/Pagination";
import EmptyState from "../../common/components/feedback/EmptyState";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import type { InquiryId } from "../../entities/inquiry/inquiryIdentifiers";
import CompactConsultationDesk from "../../features/consultation/components/CompactConsultationDesk";
import useCounselorQueueFilters from "../../features/consultation/hooks/useCounselorQueueFilters";
import { CONSULTANT_QUEUE_INQUIRIES } from "../../features/consultation/model/consultantWorkspaceMock";
import {
  formatWaitingTime,
  getCounselorQueuePage,
  getStatusBadgeVariant,
  STATUS_LABELS,
} from "../../features/consultation/model/consultantWorkspaceModel";
import type {
  CounselorAssigneeFilter,
  CounselorRisk,
} from "../../features/consultation/model/consultantWorkspaceTypes";
import "./ConsultantDashboardPage.css";

const DEFAULT_SELECTED_INQUIRY =
  CONSULTANT_QUEUE_INQUIRIES.find(
    (inquiry) => inquiry.status === "CONSULTATION_IN_PROGRESS",
  )?.inquiryId ??
  CONSULTANT_QUEUE_INQUIRIES[0]?.inquiryId ??
  null;

export default function ConsultantDashboardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { filters, hasChangedConditions, resetFilters, setFilters } =
    useCounselorQueueFilters();
  const [selectedInquiryId, setSelectedInquiryId] = useState<InquiryId | null>(
    DEFAULT_SELECTED_INQUIRY,
  );
  const mockState = new URLSearchParams(location.search).get("mockState");
  const loadState = ["loading", "error", "forbidden"].includes(
    mockState ?? "",
  )
    ? (mockState as "loading" | "error" | "forbidden")
    : "ready";
  const sourceInquiries = useMemo(
    () => (mockState === "empty" ? [] : CONSULTANT_QUEUE_INQUIRIES),
    [mockState],
  );

  useEffect(() => {
    document.body.classList.add("compact-consultant-body");
    return () => document.body.classList.remove("compact-consultant-body");
  }, []);

  const queuePage = useMemo(
    () => getCounselorQueuePage(sourceInquiries, filters),
    [filters, sourceInquiries],
  );
  const selectedInquiry =
    queuePage.items.find((item) => item.inquiryId === selectedInquiryId) ??
    queuePage.items.find(
      (item) => item.status === "CONSULTATION_IN_PROGRESS",
    ) ??
    queuePage.items[0] ??
    null;

  const handleOpenVisit = (
    entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED",
  ) => {
    if (!selectedInquiry) return;
    navigate(createVisitTransitionPath(selectedInquiry.inquiryId), {
      state: {
        returnTo: `/consultant/inquiries${location.search}`,
        stateVersion: selectedInquiry.stateVersion,
        symptomSummary: selectedInquiry.symptomLabel,
        entryAction,
      },
    });
  };

  return (
    <div className="simple-consultant-app">
      <header className="simple-topbar">
        <a className="simple-brand" href="/" aria-label="워터케어 홈으로 이동">
          <span aria-hidden="true">W</span>
          <strong>워터케어 ONE</strong>
        </a>

        <span className="simple-topbar__notice">
          <i aria-hidden="true" /> 상담 화면 · Mock 데이터
        </span>

        <div className="simple-user">
          <span>{user?.displayName.slice(0, 1) ?? "상"}</span>
          <strong>{user?.displayName ?? "상담사"}</strong>
        </div>
      </header>

      <main className="simple-consultant-main">
        <section className="simple-page-head" aria-labelledby="simple-page-title">
          <div>
            <h1 id="simple-page-title">상담·문의 큐</h1>
            <p>문의 하나를 선택하고 필요한 다음 처리만 진행하세요.</p>
          </div>
          <b>처리 대상 {queuePage.totalItems}건</b>
        </section>

        <section className="simple-workspace">
          <aside className="simple-inbox" aria-label="상담 문의 목록">
            <header className="simple-inbox__head">
              <div>
                <small>MY QUEUE</small>
                <h2>처리할 문의</h2>
              </div>
              <strong>{queuePage.totalItems}</strong>
            </header>

            <div className="simple-search-row">
              <label className="simple-search">
                <span aria-hidden="true">⌕</span>
                <input
                  type="search"
                  aria-label="문의 검색"
                  value={filters.query}
                  onChange={(event) =>
                    setFilters({ ...filters, query: event.target.value, page: 1 })
                  }
                  placeholder="고객, 증상, 문의번호 검색"
                />
              </label>
              {hasChangedConditions && (
                <button type="button" onClick={resetFilters}>
                  초기화
                </button>
              )}
            </div>

            <details className="simple-filter-panel">
              <summary>추가 필터</summary>
              <div>
                <label>
                  <span>위험도</span>
                  <select
                    aria-label="위험도"
                    value={filters.risk}
                    onChange={(event) =>
                      setFilters({
                        ...filters,
                        risk: event.target.value as "ALL" | CounselorRisk,
                        page: 1,
                      })
                    }
                  >
                    <option value="ALL">전체</option>
                    <option value="DANGER">긴급</option>
                    <option value="CAUTION">주의</option>
                  </select>
                </label>
                <label>
                  <span>담당자</span>
                  <select
                    aria-label="담당자"
                    value={filters.assignee}
                    onChange={(event) =>
                      setFilters({
                        ...filters,
                        assignee: event.target.value as CounselorAssigneeFilter,
                        page: 1,
                      })
                    }
                  >
                    <option value="ALL">전체</option>
                    <option value="MINE">내 담당</option>
                    <option value="UNASSIGNED">미배정</option>
                  </select>
                </label>
              </div>
            </details>

            <div className="simple-inbox__list">
              {loadState === "loading" ? (
                <LoadingState
                  title="상담 문의 목록을 불러오고 있습니다."
                  description="잠시만 기다려 주세요."
                />
              ) : loadState === "error" ? (
                <ErrorState
                  title="상담 문의 목록을 불러오지 못했습니다."
                  description="잠시 후 다시 시도해 주세요."
                  onRetry={() => navigate("/consultant/inquiries", { replace: true })}
                />
              ) : loadState === "forbidden" ? (
                <ForbiddenState
                  title="상담 문의 목록을 볼 권한이 없습니다."
                  description="상담사 역할과 담당 범위를 확인해 주세요."
                />
              ) : queuePage.items.length === 0 ? (
                <EmptyState
                  title={
                    hasChangedConditions
                      ? "조건에 맞는 문의가 없습니다."
                      : "아직 접수된 문의가 없습니다."
                  }
                  description={
                    hasChangedConditions
                      ? "검색어를 바꾸거나 초기화해 주세요."
                      : "새 문의가 들어오면 여기에 표시됩니다."
                  }
                  actionLabel={hasChangedConditions ? "조건 초기화" : undefined}
                  onAction={hasChangedConditions ? resetFilters : undefined}
                />
              ) : (
                queuePage.items.map((inquiry) => (
                  <button
                    key={inquiry.inquiryId}
                    className={`v6-queue-item simple-inquiry-card${
                      selectedInquiry?.inquiryId === inquiry.inquiryId
                        ? " is-selected"
                        : ""
                    }`}
                    type="button"
                    aria-pressed={selectedInquiry?.inquiryId === inquiry.inquiryId}
                    onClick={() => setSelectedInquiryId(inquiry.inquiryId)}
                  >
                    <span className="simple-inquiry-card__meta">
                      <RiskBadge
                        level={inquiry.riskLevel.toLowerCase()}
                        size="compact"
                      />
                      <em>대기 {formatWaitingTime(inquiry.waitingMinutes)}</em>
                    </span>
                    <strong>{inquiry.symptomLabel}</strong>
                    <span className="simple-inquiry-card__customer">
                      {inquiry.customerDisplayName} · {inquiry.productCode}
                    </span>
                    <span className="simple-inquiry-card__status">
                      <StatusBadge
                        label={STATUS_LABELS[inquiry.status]}
                        size="compact"
                        variant={getStatusBadgeVariant(inquiry.status)}
                      />
                      <small>{inquiry.inquiryCode}</small>
                    </span>
                  </button>
                ))
              )}
            </div>

            {loadState === "ready" && queuePage.totalItems > 0 && (
              <Pagination
                page={queuePage.currentPage}
                totalItems={queuePage.totalItems}
                totalPages={queuePage.totalPages}
                onPageChange={(page) => setFilters({ ...filters, page })}
              />
            )}
          </aside>

          <CompactConsultationDesk
            key={selectedInquiry?.inquiryId ?? "empty"}
            inquiry={selectedInquiry}
            onOpenFullDetail={() => {
              if (!selectedInquiry) return;
              navigate(createInquiryDetailPath(selectedInquiry.inquiryId), {
                state: { returnTo: `/consultant/inquiries${location.search}` },
              });
            }}
            onOpenVisit={handleOpenVisit}
          />
        </section>
      </main>
    </div>
  );
}
