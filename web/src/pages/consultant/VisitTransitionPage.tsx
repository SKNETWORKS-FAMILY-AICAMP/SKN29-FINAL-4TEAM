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
import { getCounselorMetrics } from "../../features/consultation/model/consultantWorkspaceModel";
import { consultantWorkspaceRepository } from "../../features/consultation/repositories/consultantWorkspaceRepository";
import VisitTransitionForm from "../../features/visit-transition/components/VisitTransitionForm";
import type { VisitMockAction } from "../../features/visit-transition/model/visitTransitionTypes";
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

export default function VisitTransitionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { inquiryId: rawInquiryId } = useParams<{ inquiryId: string }>();
  const [notificationOpen, setNotificationOpen] = useState(false);

  const locationState = location.state as VisitTransitionLocationState | null;
  const inquiryListReturnPath = getSafeInquiryListReturnPath(
    locationState?.returnTo,
  );
  const inquiryId = rawInquiryId ? toInquiryId(rawInquiryId) : null;
  const inquiry = consultantWorkspaceRepository.findInquiry(inquiryId);
  const [stateVersion, setStateVersion] = useState(
    locationState?.stateVersion ?? inquiry?.stateVersion ?? 1,
  );
  const [lastAction, setLastAction] = useState<VisitMockAction | null>(null);
  const allowedActionCodes = inquiry?.allowedActions.map((item) => item.code) ?? [];
  const availableMockActions: VisitMockAction[] = [];
  if (
    allowedActionCodes.includes("VISIT_NEEDED") ||
    locationState?.entryAction === "VISIT_REVIEW_REQUIRED"
  ) {
    availableMockActions.push("CREATE_VISIT_REQUEST");
  }
  if (
    allowedActionCodes.includes("UPDATE_VISIT_SCHEDULE") ||
    locationState?.entryAction === "VISIT_NEEDED" ||
    lastAction === "CREATE_VISIT_REQUEST"
  ) {
    availableMockActions.push("SAVE_SCHEDULE");
  }
  if (
    allowedActionCodes.includes("CONFIRM_VISIT") ||
    lastAction === "SAVE_SCHEDULE"
  ) {
    availableMockActions.push("CONFIRM_VISIT");
  }

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
    if (target === "detail" && inquiry) {
      navigate(createInquiryDetailPath(inquiry.inquiryId), {
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
      {!inquiry ? (
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
      ) : availableMockActions.length === 0 ? (
        <section className="v6-panel visit-v13-access-blocked">
          <ForbiddenState
            title="현재 상태에서는 방문 전환을 처리할 수 없습니다."
            description="Backend Mock allowed_actions에 방문 필요 확정·일정 조율·방문 확정 행동이 없습니다."
            actionLabel="상담 큐로 돌아가기"
            onAction={() => navigate(inquiryListReturnPath)}
          />
        </section>
      ) : (
        <div id="visit-transition-form" className="visit-v13-page">
          <header className="v6-page-head visit-v13-page-head">
            <div className="v6-page-head__copy">
              <small>CONS-03 · SCREEN DESIGN V13</small>
              <h1>방문 전환·일정 등록</h1>
              <p>
                상담에서 확인한 고객 증상과 안전 조치를 보존한 채 가상 기사에게
                전달하고, 희망일과 확정일을 구분해 시연합니다.
              </p>
            </div>
            <div className="v6-page-head__meta">
              <span>문의 · {inquiry.inquiryCode}</span>
              <span>제품 · {inquiry.productCode}</span>
              <span>실제 API 연결 없음</span>
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
              <span>
                방문 상태 ·{" "}
                {lastAction === "CONFIRM_VISIT"
                  ? "방문 확정 Mock"
                  : lastAction === "CREATE_VISIT_REQUEST"
                    ? "방문 요청 생성 Mock"
                    : availableMockActions.includes("CREATE_VISIT_REQUEST")
                      ? "방문 필요 검토 Mock"
                      : "일정 조율 Mock"}
              </span>
              <span>상태 버전 · {stateVersion}</span>
            </div>
          </div>

          <VisitTransitionForm
            key={inquiry.inquiryId}
            availableActions={availableMockActions}
            inquiry={inquiry}
            stateVersion={stateVersion}
            symptomSummary={
              locationState?.symptomSummary ?? inquiry.symptomLabel
            }
            onMockSaved={(nextVersion, action) => {
              setStateVersion(nextVersion);
              setLastAction(action);
            }}
          />
        </div>
      )}
    </ConsultantWorkspaceLayout>
  );
}
