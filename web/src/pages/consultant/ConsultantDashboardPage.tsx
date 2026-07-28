import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createVisitTransitionPath } from "../../app/router/routePaths";
import ConsultantInquiryDetail from "../../features/consultation/components/ConsultantInquiryDetail";
import ConsultantQueue from "../../features/consultation/components/ConsultantQueue";
import ConsultantWorkspaceLayout from "../../features/consultation/components/ConsultantWorkspaceLayout";
import { COUNSELOR_INQUIRIES } from "../../features/consultation/model/consultantWorkspaceMock";
import {
  filterCounselorInquiries,
  getCounselorMetrics,
} from "../../features/consultation/model/consultantWorkspaceModel";
import type {
  CounselorFilters,
  DetailTab,
} from "../../features/consultation/model/consultantWorkspaceTypes";
import "../../common/styles/legacy/fix-base.css";
import "../../common/styles/legacy/staff-desktop-v6.css";

const INITIAL_FILTERS: CounselorFilters = {
  query: "",
  status: "ALL",
  risk: "ALL",
  consultation: "ALL",
};

export default function ConsultantDashboardPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [selectedInquiryId, setSelectedInquiryId] = useState<string | null>(
    COUNSELOR_INQUIRIES[0]?.id ?? null,
  );
  const [detailTab, setDetailTab] = useState<DetailTab>("summary");
  const [notificationOpen, setNotificationOpen] = useState(false);

  useEffect(() => {
    document.body.classList.add("v6-body", "v6-body--counselor");

    return () => {
      document.body.classList.remove("v6-body", "v6-body--counselor");
    };
  }, []);

  const inquiries = useMemo(
    () => filterCounselorInquiries(COUNSELOR_INQUIRIES, filters),
    [filters],
  );
  const metrics = useMemo(
    () => getCounselorMetrics(inquiries),
    [inquiries],
  );
  const selectedInquiry =
    inquiries.find((item) => item.id === selectedInquiryId) ??
    inquiries[0] ??
    null;
  const visibleSelectedInquiryId = selectedInquiry?.id ?? null;
  const queueCount =
    metrics.consultation +
    metrics.danger +
    metrics.finalizable;

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  const handleNavigate = (target: "queue" | "detail" | "visit") => {
    if (target === "queue") {
      scrollTo("counselor-queue-filter");
      return;
    }

    if (target === "detail") {
      scrollTo("counselor-detail");
      return;
    }

    if (selectedInquiry) {
      scrollTo("counselor-action-panel");
    }
  };

  const handleOpenVisit = () => {
    if (!selectedInquiry) return;

    navigate(createVisitTransitionPath(selectedInquiry.id), {
      state: {
        returnTo: "/consultant/inquiries",
        stateVersion: selectedInquiry.stateVersion,
        symptomSummary: selectedInquiry.symptomLabel,
      },
    });
  };

  return (
    <ConsultantWorkspaceLayout
      notificationOpen={notificationOpen}
      queueCount={queueCount}
      onCloseNotifications={() => setNotificationOpen(false)}
      onNavigate={handleNavigate}
      onToggleNotifications={() => setNotificationOpen((open) => !open)}
    >
      <header className="v6-page-head">
        <div className="v6-page-head__copy">
          <small>CONS-01 · CONS-02 · CONS-03</small>
          <h1>상담·문의 큐</h1>
          <p>
            위험·상담 필수·최종 완료 대기 순으로 확인하고, 고객 원문과
            공식 근거를 보존한 채 방문기사에게 인계합니다.
          </p>
        </div>
        <div className="v6-page-head__meta">
          <span>고정 상담원 · 한유진</span>
          <span>공식 모델 · WPUJAC104DWH</span>
          <span>담당·미배정 합성 문의 · {inquiries.length}건</span>
        </div>
      </header>

      <section className="v6-metric-grid" aria-label="상담 업무 요약">
        <article className="v6-metric-card is-warning">
          <div>
            <span>상담 대기</span>
            <i>◷</i>
          </div>
          <strong>{metrics.consultation}</strong>
          <small>신규·재개 상담 시작 필요</small>
        </article>
        <article className="v6-metric-card is-danger">
          <div>
            <span>위험 문의</span>
            <i>!</i>
          </div>
          <strong>{metrics.danger}</strong>
          <small>사용·음용 중지 우선</small>
        </article>
        <article className="v6-metric-card">
          <div>
            <span>방문 진행</span>
            <i>□</i>
          </div>
          <strong>{metrics.visit}</strong>
          <small>검토·조율·확정·재방문</small>
        </article>
        <article className="v6-metric-card is-safe">
          <div>
            <span>최종 완료 가능</span>
            <i>✓</i>
          </div>
          <strong>{metrics.finalizable}</strong>
          <small>고객 해결 피드백 도착</small>
        </article>
      </section>

      <ConsultantQueue
        filters={filters}
        inquiries={inquiries}
        selectedInquiryId={visibleSelectedInquiryId}
        onFiltersChange={setFilters}
        onSelectInquiry={(inquiryId) => {
          setSelectedInquiryId(inquiryId);
          setDetailTab("summary");
        }}
      >
        <ConsultantInquiryDetail
          detailTab={detailTab}
          inquiry={selectedInquiry}
          onDetailTabChange={setDetailTab}
          onOpenVisit={handleOpenVisit}
        />
      </ConsultantQueue>
    </ConsultantWorkspaceLayout>
  );
}
