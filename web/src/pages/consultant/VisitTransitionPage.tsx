import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import {
  createInquiryDetailPath,
  getSafeInquiryListReturnPath,
  ROUTE_PATHS,
} from "../../app/router/routePaths";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import "../../common/styles/legacy/fix-base.css";
import "../../common/styles/legacy/staff-desktop-v6.css";
import { toInquiryId } from "../../entities/inquiry/inquiryIdentifiers";
import ConsultantWorkspaceLayout from "../../features/consultation/components/ConsultantWorkspaceLayout";
import { useConsultantInquiryDetailQuery } from "../../features/consultation/hooks/useConsultantWorkspaceQueries";
import { getCounselorMetrics } from "../../features/consultation/model/consultantWorkspaceModel";
import { consultantWorkspaceDataRepository } from "../../features/consultation/repositories/consultantWorkspaceDataRepository";
import { consultantWorkspaceRepository } from "../../features/consultation/repositories/consultantWorkspaceRepository";
import { getSyntheticConsultantDashboardData } from "../../features/notice/api/consultantNoticeApi";
import type { ConsultantDashboardTechnician } from "../../features/notice/model/consultantNotice";
import RemoteVisitTransitionPanel, {
  type TechnicianSourceStatus,
} from "../../features/visit-transition/components/RemoteVisitTransitionPanel";
import { classifyTechnicianSourceFailure } from "../../features/visit-transition/model/technicianSource";
import VisitTransitionForm from "../../features/visit-transition/components/VisitTransitionForm";
import "./VisitTransitionPage.css";
import "../../common/styles/water-glass-theme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";

interface VisitTransitionLocationState {
  entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED";
  returnTo?: unknown;
  stateVersion?: number;
  symptomSummary?: string;
}

interface TechnicianSourceState {
  status: TechnicianSourceStatus;
  technicians: readonly ConsultantDashboardTechnician[];
}

export default function VisitTransitionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { inquiryId: rawInquiryId } = useParams<{ inquiryId: string }>();
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [technicianSource, setTechnicianSource] =
    useState<TechnicianSourceState>({
      status: "loading",
      technicians: [],
    });
  const [technicianSourceRetryCount, setTechnicianSourceRetryCount] =
    useState(0);

  const locationState = location.state as VisitTransitionLocationState | null;
  const inquiryListReturnPath = getSafeInquiryListReturnPath(
    locationState?.returnTo,
  );
  const inquiryId = rawInquiryId ? toInquiryId(rawInquiryId) : null;
  const isRemote = consultantWorkspaceDataRepository.dataSource === "REMOTE";
  const detailQuery = useConsultantInquiryDetailQuery(inquiryId);
  const remoteInquiry = isRemote ? detailQuery.data : null;
  const inquiry = isRemote ? undefined : consultantWorkspaceRepository.findInquiry(inquiryId);
  const stateVersion = locationState?.stateVersion ?? inquiry?.stateVersion ?? 1;
  const allowedActionCodes = new Set(
    inquiry?.allowedActions.map((item) => item.code) ?? [],
  );
  const hasAvailableVisitAction =
    locationState?.entryAction === "VISIT_REVIEW_REQUIRED" ||
    locationState?.entryAction === "VISIT_NEEDED" ||
    allowedActionCodes.has("VISIT_NEEDED") ||
    allowedActionCodes.has("UPDATE_VISIT_SCHEDULE") ||
    allowedActionCodes.has("CONFIRM_VISIT");

  useEffect(() => {
    document.body.classList.add("v6-body", "v6-body--counselor");
    return () => {
      document.body.classList.remove("v6-body", "v6-body--counselor");
    };
  }, []);

  useEffect(() => {
    if (!isRemote) return;

    let active = true;

    void getSyntheticConsultantDashboardData().then(
      (dashboard) => {
        if (!active) return;
        setTechnicianSource({
          status: dashboard.technicians.length === 0 ? "empty" : "ready",
          technicians: dashboard.technicians,
        });
      },
      (caught: unknown) => {
        if (!active) return;
        setTechnicianSource({
          status: classifyTechnicianSourceFailure(caught),
          technicians: [],
        });
      },
    );

    return () => {
      active = false;
    };
  }, [isRemote, technicianSourceRetryCount]);

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
    const targetInquiryId = inquiry?.inquiryId ?? (remoteInquiry ? toInquiryId(remoteInquiry.inquiryId) : null);
    if (target === "detail" && targetInquiryId) {
      navigate(createInquiryDetailPath(targetInquiryId), {
        state: { returnTo: inquiryListReturnPath },
      });
      return;
    }
    document.getElementById("visit-transition-form")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  return (
    <ConsultantWorkspaceLayout
      activeSection="visit"
      notificationOpen={notificationOpen}
      queueCount={queueCount}
      onCloseNotifications={() => setNotificationOpen(false)}
      onNavigate={handleNavigate}
      onToggleNotifications={() => setNotificationOpen((open) => !open)}
    >
      {isRemote ? (
        remoteInquiry ? (
          <div id="visit-transition-form" className="visit-v13-page">
            <header className="v6-page-head visit-v13-page-head">
              <div className="v6-page-head__copy">
                <small>CONS-03 · REMOTE</small>
                <h1>방문 전환·일정 등록</h1>
                <p>Backend allowed_actions와 state_version을 기준으로 방문 흐름을 진행합니다.</p>
              </div>
              <div className="v6-page-head__meta">
                <span>문의 · {remoteInquiry.inquiryCode}</span>
                <span>상태 · {remoteInquiry.status}</span>
                <span>실제 API 연결</span>
              </div>
            </header>
            <div className="visit-v13-toolbar">
              <button className="v6-button v6-button--secondary" type="button" onClick={() => navigate(inquiryListReturnPath)}>상담 큐</button>
              <button className="v6-button v6-button--secondary" type="button" onClick={() => inquiryId && navigate(createInquiryDetailPath(inquiryId), { state: { returnTo: inquiryListReturnPath } })}>문의 상세 보기</button>
            </div>
            <RemoteVisitTransitionPanel
              inquiry={remoteInquiry}
              onRefresh={detailQuery.retry}
              onRetryTechnicians={() => {
                setTechnicianSource({ status: "loading", technicians: [] });
                setTechnicianSourceRetryCount((current) => current + 1);
              }}
              technicianSourceStatus={technicianSource.status}
              technicians={technicianSource.technicians}
            />
          </div>
        ) : (
          <section className="v6-panel visit-v13-not-found">
            <h1>{detailQuery.status === "loading" ? "문의 정보를 불러오는 중입니다." : "방문 전환 문의를 불러오지 못했습니다."}</h1>
            <button className="v6-button v6-button--primary" type="button" onClick={detailQuery.retry}>다시 시도</button>
          </section>
        )
      ) : !inquiry ? (
        <section className="v6-panel visit-v13-not-found">
          <span aria-hidden="true">□</span>
          <h1>방문 전환 문의를 찾을 수 없습니다.</h1>
          <p>합성 Mock 목록에서 문의를 다시 선택해 주세요.</p>
          <button
            className="v6-button v6-button--primary"
            type="button"
            onClick={() => navigate(ROUTE_PATHS.consultantInquiryList)}
          >
            상담 큐로 돌아가기
          </button>
        </section>
      ) : !hasAvailableVisitAction ? (
        <section className="v6-panel visit-v13-access-blocked">
          <ForbiddenState
            title="현재 상태에서는 방문 전환을 처리할 수 없습니다."
            description="allowed_actions에 방문 전환 행동이 없습니다."
            actionLabel="상담 큐로 돌아가기"
            onAction={() => navigate(inquiryListReturnPath)}
          />
        </section>
      ) : (
        <div id="visit-transition-form" className="visit-v13-page">
          <header className="v6-page-head visit-v13-page-head">
            <div className="v6-page-head__copy">
              <small>CONS-03 · API UNAVAILABLE</small>
              <h1>방문 전환·일정 등록</h1>
              <p>
                상담에서 확인한 고객 증상과 안전 조치를 확인할 수 있습니다. 기사
                선택·배정은 Backend API가 제공될 때까지 비활성화됩니다.
              </p>
            </div>
            <div className="v6-page-head__meta">
              <span>문의 · {inquiry.inquiryCode}</span>
              <span>제품 · {inquiry.productCode}</span>
              <span>기사 선택·배정 API 미지원</span>
            </div>
          </header>

          <div className="visit-v13-toolbar">
            <button
              className="v6-button v6-button--secondary"
              type="button"
              onClick={() => navigate(inquiryListReturnPath)}
            >
              ← 상담 큐
            </button>
            <button
              className="v6-button v6-button--secondary"
              type="button"
              onClick={() =>
                navigate(createInquiryDetailPath(inquiry.inquiryId), {
                  state: { returnTo: inquiryListReturnPath },
                })
              }
            >
              문의 상세 보기
            </button>
            <div>
              <span>기사 선택·배정 · 비활성화</span>
              <span>상태 버전 · {stateVersion}</span>
            </div>
          </div>

          <VisitTransitionForm
            key={inquiry.inquiryId}
            inquiry={inquiry}
            stateVersion={stateVersion}
            symptomSummary={
              locationState?.symptomSummary ?? inquiry.symptomLabel
            }
          />
        </div>
      )}
    </ConsultantWorkspaceLayout>
  );
}
