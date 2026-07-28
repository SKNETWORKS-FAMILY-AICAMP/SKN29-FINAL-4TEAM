import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import {
  createInquiryDetailPath,
  getSafeInquiryListReturnPath,
  ROUTE_PATHS,
} from "../../app/router/routePaths";
import "../../common/styles/legacy/fix-base.css";
import "../../common/styles/legacy/staff-desktop-v6.css";
import ConsultantWorkspaceLayout from "../../features/consultation/components/ConsultantWorkspaceLayout";
import { COUNSELOR_INQUIRIES } from "../../features/consultation/model/consultantWorkspaceMock";
import { getCounselorMetrics } from "../../features/consultation/model/consultantWorkspaceModel";
import VisitTransitionForm from "../../features/visit-transition/components/VisitTransitionForm";
import type { VisitMockAction } from "../../features/visit-transition/model/visitTransitionTypes";
import "./VisitTransitionPage.css";

interface VisitTransitionLocationState {
  returnTo?: unknown;
  stateVersion?: number;
  symptomSummary?: string;
}

export default function VisitTransitionPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { inquiryId } = useParams<{ inquiryId: string }>();
  const [notificationOpen, setNotificationOpen] = useState(false);

  const locationState = location.state as VisitTransitionLocationState | null;
  const inquiryListReturnPath = getSafeInquiryListReturnPath(
    locationState?.returnTo,
  );
  const inquiry = COUNSELOR_INQUIRIES.find((item) => item.id === inquiryId);
  const [stateVersion, setStateVersion] = useState(
    locationState?.stateVersion ?? inquiry?.stateVersion ?? 1,
  );
  const [lastAction, setLastAction] = useState<VisitMockAction | null>(null);

  useEffect(() => {
    document.body.classList.add("v6-body", "v6-body--counselor");
    return () => {
      document.body.classList.remove("v6-body", "v6-body--counselor");
    };
  }, []);

  const metrics = useMemo(
    () => getCounselorMetrics(COUNSELOR_INQUIRIES),
    [],
  );
  const queueCount = metrics.consultation + metrics.danger + metrics.finalizable;

  const handleNavigate = (target: "queue" | "detail" | "visit") => {
    if (target === "queue") {
      navigate(inquiryListReturnPath);
      return;
    }
    if (target === "detail" && inquiryId) {
      navigate(createInquiryDetailPath(inquiryId), {
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
              <span>문의 · {inquiry.id}</span>
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
                navigate(createInquiryDetailPath(inquiry.id), {
                  state: { returnTo: inquiryListReturnPath },
                })
              }
            >
              문의 상세 보기
            </button>
            <div>
              <span>방문 상태 · {lastAction === "CONFIRM_VISIT" ? "방문 확정 Mock" : "일정 조율 Mock"}</span>
              <span>상태 버전 · {stateVersion}</span>
            </div>
          </div>

          <VisitTransitionForm
            key={inquiry.id}
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
