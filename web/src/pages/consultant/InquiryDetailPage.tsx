import { useLocation, useNavigate, useParams } from "react-router-dom";

import {
  createVisitTransitionPath,
  getSafeInquiryListReturnPath,
} from "../../app/router/routePaths";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import AiSummarySection from "../../features/inquiry-detail/components/AiSummarySection";
import CustomerProductSection from "../../features/inquiry-detail/components/CustomerProductSection";
import EvidenceSection from "../../features/inquiry-detail/components/EvidenceSection";
import InquiryHeader from "../../features/inquiry-detail/components/InquiryHeader";
import StatusHistorySection from "../../features/inquiry-detail/components/StatusHistorySection";
import SymptomQuestionnaireSection from "../../features/inquiry-detail/components/SymptomQuestionnaireSection";
import useInquiryResponseForm from "../../features/inquiry-detail/hooks/useInquiryResponseForm";
import useMockInquiryDetail from "../../features/inquiry-detail/hooks/useMockInquiryDetail";
import { canPerformInquiryAction } from "../../features/inquiry-detail/model/inquiryDetailMapper";
import "./InquiryDetailPage.css";

interface InquiryDetailLocationState {
  returnTo?: unknown;
}

export default function InquiryDetailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { inquiryId } = useParams<{ inquiryId: string }>();

  const locationState = location.state as InquiryDetailLocationState | null;
  const inquiryListReturnPath = getSafeInquiryListReturnPath(
    locationState?.returnTo,
  );
  const inquiryQuery = useMockInquiryDetail(inquiryId);
  const initialResponseDraft =
    inquiryQuery.status === "success"
      ? inquiryQuery.data.responseDraft
      : "";
  const {
    actionMessage,
    responseDraft,
    setActionMessage,
    setResponseDraft,
  } = useInquiryResponseForm(inquiryId, initialResponseDraft);

  if (inquiryQuery.status === "loading") {
    return (
      <main className="inquiry-detail">
        <LoadingState
          title="문의 정보를 불러오고 있습니다."
          description="고객 문의와 상담 정보를 확인하고 있습니다."
        />
      </main>
    );
  }

  if (inquiryQuery.status === "error") {
    return (
      <main className="inquiry-detail">
        <ErrorState
          title="문의 정보를 불러오지 못했습니다."
          description="일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
          retryLabel="다시 시도"
          onRetry={() => window.location.reload()}
        />
      </main>
    );
  }

  if (inquiryQuery.status === "forbidden") {
    return (
      <main className="inquiry-detail">
        <ForbiddenState
          title="이 문의에 접근할 권한이 없습니다."
          description="담당 상담사이거나 해당 문의의 조회 권한이 있는지 확인해 주세요."
          actionLabel="문의 목록으로 돌아가기"
          onAction={() => navigate(inquiryListReturnPath)}
        />
      </main>
    );
  }

  if (inquiryQuery.status === "notFound") {
    return (
      <main className="inquiry-detail">
        <section className="inquiry-detail__not-found">
          <p className="inquiry-detail__eyebrow">CONS-02</p>
          <h1>문의를 찾을 수 없습니다.</h1>
          <p>문의 번호를 다시 확인해 주세요.</p>

          <button
            type="button"
            onClick={() => navigate(inquiryListReturnPath)}
          >
            문의 목록으로 돌아가기
          </button>
        </section>
      </main>
    );
  }

  const inquiry = inquiryQuery.data;

  const handleSaveDraft = () => {
    setActionMessage(
      `답변 초안을 임시 저장했습니다. 현재 상태 버전: ${inquiry.stateVersion}`,
    );
  };

  const handleSendResponse = () => {
    if (responseDraft.trim().length === 0) {
      setActionMessage("고객에게 보낼 답변을 입력해 주세요.");
      return;
    }

    setActionMessage(
      "Mock 답변 발송 요청이 완료되었습니다. 실제 API 연동 전에는 고객에게 전송되지 않습니다.",
    );
  };

  const handleRequestVisit = () => {
    navigate(createVisitTransitionPath(inquiry.inquiryId), {
      state: {
        returnTo: inquiryListReturnPath,
        stateVersion: inquiry.stateVersion,
        symptomSummary: inquiry.symptomSummary,
      },
    });
  };

  return (
    <main className="inquiry-detail">
      <InquiryHeader
        inquiry={inquiry}
        onBack={() => navigate(inquiryListReturnPath)}
      />
      <CustomerProductSection inquiry={inquiry} />
      <SymptomQuestionnaireSection inquiry={inquiry} />
      <AiSummarySection summary={inquiry.aiSummary} />
      <EvidenceSection evidence={inquiry.evidence} />

      <section className="inquiry-detail__card">
        <h2>상담 답변 작성</h2>

        <label
          className="inquiry-detail__response-label"
          htmlFor="response-draft"
        >
          고객에게 보낼 답변
        </label>

        <textarea
          id="response-draft"
          className="inquiry-detail__response-textarea"
          value={responseDraft}
          onChange={(event) => setResponseDraft(event.target.value)}
          rows={7}
        />

        <div className="inquiry-detail__response-meta">
          <span>상태 버전: {inquiry.stateVersion}</span>
          <span>{responseDraft.length}자</span>
        </div>

        {inquiry.isDanger && (
          <p className="inquiry-detail__response-warning">
            위험 문의는 일반 답변 발송보다 방문 전환을 우선 검토해 주세요.
          </p>
        )}

        <div className="inquiry-detail__action-buttons">
          {canPerformInquiryAction(inquiry, "SAVE_RESPONSE_DRAFT") && (
            <button
              type="button"
              className="inquiry-detail__action-button inquiry-detail__action-button--secondary"
              onClick={handleSaveDraft}
            >
              임시 저장
            </button>
          )}

          {canPerformInquiryAction(inquiry, "SEND_RESPONSE") && (
            <button
              type="button"
              className="inquiry-detail__action-button inquiry-detail__action-button--primary"
              onClick={handleSendResponse}
              disabled={responseDraft.trim().length === 0}
            >
              고객 답변 발송
            </button>
          )}

          {canPerformInquiryAction(inquiry, "REQUEST_VISIT") && (
            <button
              type="button"
              className="inquiry-detail__action-button inquiry-detail__action-button--visit"
              onClick={handleRequestVisit}
            >
              방문 점검으로 전환
            </button>
          )}
        </div>

        {actionMessage && (
          <p
            className="inquiry-detail__action-message"
            aria-live="polite"
          >
            {actionMessage}
          </p>
        )}

        <p className="inquiry-detail__mock-notice">
          현재는 Mock 화면입니다. 실제 발송 및 상태 전환 API는 연결되지
          않았습니다.
        </p>
      </section>

      <StatusHistorySection statusHistory={inquiry.statusHistory} />
    </main>
  );
}
