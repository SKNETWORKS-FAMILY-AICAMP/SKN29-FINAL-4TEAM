import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import {
  createVisitTransitionPath,
  getSafeInquiryListReturnPath,
  ROUTE_PATHS,
} from "../../app/router/routePaths";
import { ApiClientError } from "../../common/api/apiError";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import "../../common/styles/legacy/fix-base.css";
import "../../common/styles/legacy/staff-desktop-v6.css";
import { toInquiryId } from "../../entities/inquiry/inquiryIdentifiers";
import ConsultantInquiryDetail, {
  type ConsultantDetailSectionStates,
} from "../../features/consultation/components/ConsultantInquiryDetail";
import RemoteConsultantInquiryDetail from "../../features/consultation/components/RemoteConsultantInquiryDetail";
import ConsultantWorkspaceLayout from "../../features/consultation/components/ConsultantWorkspaceLayout";
import { useConsultantInquiryDetailQuery } from "../../features/consultation/hooks/useConsultantWorkspaceQueries";
import { getCounselorMetrics } from "../../features/consultation/model/consultantWorkspaceModel";
import type { DetailTab } from "../../features/consultation/model/consultantWorkspaceTypes";
import { consultantWorkspaceDataRepository } from "../../features/consultation/repositories/consultantWorkspaceDataRepository";
import { consultantWorkspaceRepository } from "../../features/consultation/repositories/consultantWorkspaceRepository";
import "./InquiryDetailPage.css";
import "../../common/styles/water-glass-theme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";

interface InquiryDetailLocationState {
  returnTo?: unknown;
}

const PARTIAL_FAILURES: Record<string, ConsultantDetailSectionStates> = {
  ai: { aiSummary: "error", evidence: "ready", timeline: "ready" },
  evidence: { aiSummary: "ready", evidence: "error", timeline: "ready" },
  timeline: { aiSummary: "ready", evidence: "ready", timeline: "error" },
};

const READY_SECTIONS: ConsultantDetailSectionStates = {
  aiSummary: "ready",
  evidence: "ready",
  timeline: "ready",
};

export default function InquiryDetailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { inquiryId: rawInquiryId } = useParams<{ inquiryId: string }>();
  const [detailTab, setDetailTab] = useState<DetailTab>("summary");
  const [notificationOpen, setNotificationOpen] = useState(false);

  const locationState = location.state as InquiryDetailLocationState | null;
  const inquiryListReturnPath = getSafeInquiryListReturnPath(
    locationState?.returnTo,
  );
  const inquiryId = rawInquiryId ? toInquiryId(rawInquiryId) : null;
  const query = new URLSearchParams(location.search);
  const partialFailure = PARTIAL_FAILURES[query.get("mockFailure") ?? ""];
  const mockState = query.get("mockState");
  const detailQuery = useConsultantInquiryDetailQuery(inquiryId);
  const inquiry =
    consultantWorkspaceDataRepository.dataSource === "MOCK"
      ? consultantWorkspaceRepository.findInquiry(inquiryId)
      : undefined;
  const remoteDetail =
    consultantWorkspaceDataRepository.dataSource === "REMOTE"
      ? detailQuery.data
      : null;
  const loadState = mockState
    ? mockState
    : consultantWorkspaceDataRepository.dataSource === "MOCK"
      ? "ready"
      : detailQuery.isForbidden
        ? "forbidden"
        : detailQuery.isNotFound
          ? "not_found"
          : detailQuery.status;
  const correlationId =
    detailQuery.error instanceof ApiClientError
      ? detailQuery.error.correlationId
      : undefined;

  useEffect(() => {
    document.body.classList.add("v6-body", "v6-body--counselor");
    return () => {
      document.body.classList.remove("v6-body", "v6-body--counselor");
    };
  }, []);

  const metrics = useMemo(
    () =>
      getCounselorMetrics(consultantWorkspaceRepository.listAllInquiries()),
    [],
  );
  const queueCount = metrics.consultation + metrics.danger + metrics.finalizable;

  const handleNavigate = (target: "queue" | "detail" | "visit") => {
    if (target === "queue") {
      navigate(inquiryListReturnPath);
      return;
    }
    if (target === "visit" && inquiry) {
      navigate(createVisitTransitionPath(inquiry.inquiryId), {
        state: {
          returnTo: inquiryListReturnPath,
          stateVersion: inquiry.stateVersion,
          symptomSummary: inquiry.symptomLabel,
        },
      });
      return;
    }
    document.getElementById("counselor-detail")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  const handleOpenVisit = (
    entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED",
  ) => {
    if (!inquiry) return;

    navigate(createVisitTransitionPath(inquiry.inquiryId), {
      state: {
        returnTo: inquiryListReturnPath,
        stateVersion: inquiry.stateVersion,
        symptomSummary: inquiry.symptomLabel,
        entryAction,
      },
    });
  };

  const renderDetail = () => {
    if (loadState === "loading") {
      return (
        <LoadingState
          title="문의 정보를 불러오고 있습니다."
          description="고객 문의와 상담 정보를 확인하고 있습니다."
        />
      );
    }
    if (loadState === "error") {
      return (
        <ErrorState
          title="문의 정보를 불러오지 못했습니다."
          description={
            correlationId
              ? `잠시 후 다시 시도해 주세요. 확인 번호: ${correlationId}`
              : "잠시 후 다시 시도해 주세요."
          }
          retryLabel="문의 목록으로 돌아가기"
          onRetry={
            mockState === "error"
              ? () => navigate(inquiryListReturnPath)
              : detailQuery.retry
          }
        />
      );
    }
    if (loadState === "forbidden") {
      return (
        <ForbiddenState
          title="이 문의에 접근할 권한이 없습니다."
          description="담당 상담사이거나 해당 문의의 조회 권한이 있는지 확인해 주세요."
          actionLabel="문의 목록으로 돌아가기"
          onAction={() => navigate(inquiryListReturnPath)}
        />
      );
    }
    if (loadState === "unsupported") {
      return (
        <ErrorState
          title="지원하지 않는 제품 모델입니다."
          description="현재 등록된 설명서와 모델 범위를 확인한 뒤 상담 관리자에게 문의해 주세요."
          retryLabel="문의 목록으로 돌아가기"
          onRetry={() => navigate(inquiryListReturnPath)}
        />
      );
    }
    if (loadState === "not_found") {
      return (
        <section className="v6-panel inquiry-v13-not-found">
          <span aria-hidden="true">▤</span>
          <h1>문의 정보를 찾을 수 없습니다.</h1>
          <p>문의가 없거나 현재 상담사에게 배정되지 않은 경우 동일하게 안내됩니다.</p>
          <button
            className="v6-button v6-button--primary"
            type="button"
            onClick={() => navigate(inquiryListReturnPath)}
          >
            상담 큐로 돌아가기
          </button>
        </section>
      );
    }
    if (remoteDetail) {
      return (
        <>
          <header className="v6-page-head inquiry-v13-page-head">
            <div className="v6-page-head__copy">
              <small>CONS-02 · REMOTE</small>
              <h1>문의 상세·상담 처리</h1>
              <p>Backend가 제공한 상담사 전용 상세 정보를 표시합니다.</p>
            </div>
            <div className="v6-page-head__meta">
              <span>문의 · {remoteDetail.inquiryCode}</span>
              <span>상태 버전 · {remoteDetail.stateVersion}</span>
              <span>실제 API 상세</span>
            </div>
          </header>

          <div className="inquiry-v13-toolbar">
            <button
              className="v6-button v6-button--secondary"
              type="button"
              onClick={() => navigate(inquiryListReturnPath)}
            >
              검색 조건을 유지하고 상담 큐로
            </button>
            <span>상태와 허용 행동은 Backend 응답을 기준으로 표시합니다.</span>
          </div>

          <section className="v6-panel inquiry-v13-detail-shell">
            <RemoteConsultantInquiryDetail inquiry={remoteDetail} />
          </section>
        </>
      );
    }
    if (!inquiry) {
      return (
        <section className="v6-panel inquiry-v13-not-found">
          <span aria-hidden="true">▤</span>
          <h1>문의를 찾을 수 없습니다.</h1>
          <p>합성 Mock 목록에서 문의를 다시 선택해 주세요.</p>
          <button
            className="v6-button v6-button--primary"
            type="button"
            onClick={() => navigate(ROUTE_PATHS.consultantInquiryList)}
          >
            상담 큐로 돌아가기
          </button>
        </section>
      );
    }

    return (
      <>
        <header className="v6-page-head inquiry-v13-page-head">
          <div className="v6-page-head__copy">
            <small>CONS-02 · SCREEN DESIGN V13</small>
            <h1>문의 상세·상담 처리</h1>
            <p>고객 원문, 사용 안내, AI 초안, 공식 근거와 상담사 확정 내용을 구분해 확인합니다.</p>
          </div>
          <div className="v6-page-head__meta">
            <span>문의 · {inquiry.inquiryCode}</span>
            <span>상태 버전 · {inquiry.stateVersion}</span>
            <span>합성 Mock 상세</span>
          </div>
        </header>

        <div className="inquiry-v13-toolbar">
          <button
            className="v6-button v6-button--secondary"
            type="button"
            onClick={() => navigate(inquiryListReturnPath)}
          >
            ← 검색 조건을 유지하고 상담 큐로
          </button>
          <span>실제 고객 응답·상태 변경 API는 연결되지 않았습니다.</span>
        </div>

        <section className="v6-panel inquiry-v13-detail-shell">
          <ConsultantInquiryDetail
            detailTab={detailTab}
            inquiry={inquiry}
            sectionStates={partialFailure ?? READY_SECTIONS}
            onDetailTabChange={setDetailTab}
            onOpenVisit={handleOpenVisit}
          />
        </section>
      </>
    );
  };

  return (
    <ConsultantWorkspaceLayout
      activeSection="detail"
      notificationOpen={notificationOpen}
      queueCount={queueCount}
      onCloseNotifications={() => setNotificationOpen(false)}
      onNavigate={handleNavigate}
      onToggleNotifications={() => setNotificationOpen((open) => !open)}
    >
      {renderDetail()}
    </ConsultantWorkspaceLayout>
  );
}
