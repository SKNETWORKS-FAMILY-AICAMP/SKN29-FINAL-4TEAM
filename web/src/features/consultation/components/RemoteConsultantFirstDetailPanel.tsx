import { useNavigate } from "react-router-dom";

import {
  createInquiryDetailPath,
  createVisitTransitionPath,
} from "../../../app/router/routePaths";
import ErrorState from "../../../common/components/feedback/ErrorState";
import ForbiddenState from "../../../common/components/feedback/ForbiddenState";
import LoadingState from "../../../common/components/feedback/LoadingState";
import type { InquiryId } from "../../../entities/inquiry/inquiryIdentifiers";
import { useConsultantInquiryDetailQuery } from "../hooks/useConsultantWorkspaceQueries";
import type { ConsultantWorkspaceDataRepository } from "../repositories/consultantWorkspaceDataRepository";
import RemoteConsultantInquiryDetail from "./RemoteConsultantInquiryDetail";

interface RemoteConsultantFirstDetailPanelProps {
  inquiryId: InquiryId;
  onClose: () => void;
  onRefreshWorkspace: () => void;
  repository?: ConsultantWorkspaceDataRepository;
  returnTo: string;
}

function appendCorrelationId(
  description: string,
  correlationId: string | null,
): string {
  return correlationId
    ? `${description} 확인 번호: ${correlationId}`
    : description;
}

export default function RemoteConsultantFirstDetailPanel({
  inquiryId,
  onClose,
  onRefreshWorkspace,
  repository,
  returnTo,
}: RemoteConsultantFirstDetailPanelProps) {
  const navigate = useNavigate();
  const detailQuery = useConsultantInquiryDetailQuery(inquiryId, repository);
  const inquiry = detailQuery.data;

  const refreshDetailAndWorkspace = () => {
    detailQuery.retry();
    onRefreshWorkspace();
  };

  const openVisit = (
    entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED",
  ) => {
    if (!inquiry) return;

    navigate(createVisitTransitionPath(inquiryId), {
      state: {
        entryAction,
        returnTo,
        stateVersion: inquiry.workflow.stateVersion,
        symptomSummary: inquiry.symptomAndQuestionnaire.symptomSummary,
      },
    });
  };

  const renderBody = () => {
    if (detailQuery.status === "loading" || detailQuery.status === "idle") {
      return (
        <LoadingState
          title="문의 정보를 불러오고 있습니다."
          description="고객 문의와 상담 처리 정보를 확인하고 있습니다."
        />
      );
    }

    if (detailQuery.isForbidden) {
      return (
        <ForbiddenState
          title="이 문의에 접근할 권한이 없습니다."
          description={appendCorrelationId(
            "담당 상담사이거나 해당 문의의 조회 권한이 있는지 확인해 주세요.",
            detailQuery.correlationId,
          )}
          actionLabel="패널 닫기"
          onAction={onClose}
        />
      );
    }

    if (detailQuery.isNotFound) {
      return (
        <ErrorState
          title="문의 정보를 찾을 수 없습니다."
          description={appendCorrelationId(
            "문의가 없거나 현재 상담사에게 배정되지 않은 경우 동일하게 안내됩니다.",
            detailQuery.correlationId,
          )}
          retryLabel="패널 닫기"
          onRetry={onClose}
        />
      );
    }

    if (detailQuery.isConflict) {
      return (
        <ErrorState
          title="문의 상태가 변경되었습니다."
          description={appendCorrelationId(
            "최신 문의 상태를 다시 불러와 주세요.",
            detailQuery.correlationId,
          )}
          retryLabel="최신 상태 다시 불러오기"
          onRetry={detailQuery.retry}
        />
      );
    }

    if (detailQuery.status === "error" || !inquiry) {
      return (
        <ErrorState
          title="문의 정보를 불러오지 못했습니다."
          description={appendCorrelationId(
            "입력된 내용은 변경하지 않았습니다. 잠시 후 다시 시도해 주세요.",
            detailQuery.correlationId,
          )}
          retryLabel="다시 시도"
          onRetry={detailQuery.retry}
        />
      );
    }

    return (
      <>
        <div className="remote-first-detail-toolbar">
          <button
            type="button"
            className="remote-first-detail-toolbar__history"
            onClick={() =>
              navigate(createInquiryDetailPath(inquiryId), {
                state: { returnTo },
              })
            }
          >
            전체 기록 보기
          </button>
          {detailQuery.correlationId && (
            <small>조회 확인 번호: {detailQuery.correlationId}</small>
          )}
        </div>

        <RemoteConsultantInquiryDetail
          key={inquiryId}
          inquiry={inquiry}
          onOpenVisit={openVisit}
          onRefresh={refreshDetailAndWorkspace}
        />
      </>
    );
  };

  return (
    <>
      <header className="consultant-detail-drawer__head">
        <div>
          <small>{inquiry?.inquiryCode ?? "REMOTE DETAIL"}</small>
          <h2 id="consultant-detail-title">
            {inquiry
              ? `${inquiry.customer.displayName} · ${inquiry.symptomAndQuestionnaire.symptomSummary}`
              : "문의 상세·상담 처리"}
          </h2>
          <p>Backend가 제공한 상세 정보와 허용 작업을 이 패널에서 처리합니다.</p>
        </div>
        <button type="button" aria-label="문의 상세 닫기" onClick={onClose}>
          <span aria-hidden="true">×</span>
        </button>
      </header>

      <div className="consultant-detail-drawer__body consultant-detail-drawer__body--remote">
        {renderBody()}
      </div>
    </>
  );
}
