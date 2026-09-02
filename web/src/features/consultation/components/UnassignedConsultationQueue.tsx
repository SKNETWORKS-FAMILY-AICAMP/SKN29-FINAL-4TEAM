import { useMemo, useRef, useState } from "react";

import { ApiClientError } from "../../../common/api/apiError";
import { createRequestContext } from "../../../common/api/requestContext";
import { useUnassignedConsultationQueueQuery } from "../hooks/useConsultantWorkspaceQueries";
import type { UnassignedConsultationQueueItemViewModel } from "../model/consultantWorkspaceRemoteMapper";
import { formatProductModelAndName } from "../model/productDisplayName";
import {
  consultantWorkspaceDataRepository,
  type ConsultantWorkspaceDataRepository,
} from "../repositories/consultantWorkspaceDataRepository";
import {
  createRemoteConsultationWriteRepository,
  type ConsultationWriteRepository,
} from "../repositories/consultationWriteRepository";
import "./UnassignedConsultationQueue.css";

// The queue API supports up to 100; use its standard page size so counselors
// can scan the waiting list without paging after every three inquiries.
const PAGE_SIZE = 20;
const defaultWriteRepository = createRemoteConsultationWriteRepository();

const RISK_LABELS = {
  general: "일반",
  caution: "주의",
  danger: "긴급",
} as const;

interface ClaimFeedback {
  inquiryId: string;
  kind: "error" | "success";
  message: string;
  correlationId?: string;
}

interface Props {
  dataRepository?: ConsultantWorkspaceDataRepository;
  writeRepository?: ConsultationWriteRepository;
  onClaimed: (inquiryId: string) => void;
}

function formatWaitingTime(waitingSeconds: number): string {
  const minutes = Math.max(1, Math.floor(waitingSeconds / 60));
  if (minutes < 60) return `${minutes}분 대기`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0
    ? `${hours}시간 ${remainingMinutes}분 대기`
    : `${hours}시간 대기`;
}

function getClaimErrorFeedback(
  inquiryId: string,
  error: unknown,
): ClaimFeedback {
  if (!(error instanceof ApiClientError)) {
    return {
      inquiryId,
      kind: "error",
      message: "상담을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    };
  }

  let message = "상담을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  if (error.status === 400) {
    message = "상담 요청 형식을 확인할 수 없습니다. 목록을 새로고침해 주세요.";
  } else if (error.status === 401) {
    message = "로그인이 필요하거나 로그인 정보가 만료되었습니다. 다시 로그인해 주세요.";
  } else if (error.status === 404) {
    message = "이미 배정된 문의입니다. 새로고침해주세요.";
  } else if (error.status === 409 && error.code === "STATE-CONFLICT-01") {
    message = "화면이 오래되어 문의 상태가 달라졌습니다. 최신 목록을 확인해 주세요.";
  } else if (error.status === 409 && error.code === "DUPLICATE-EVENT-01") {
    message = "같은 요청이 다른 내용으로 이미 처리되었습니다. 최신 목록을 확인해 주세요.";
  } else if (error.status === 409) {
    message = "문의 상태가 변경되었습니다. 최신 목록을 확인해 주세요.";
  } else if (error.status === 403) {
    message = "이 상담을 가져올 권한이 없습니다.";
  } else if (error.status === 422) {
    message = "요청 정보를 확인할 수 없습니다. 목록을 새로고침해 주세요.";
  }

  return {
    inquiryId,
    kind: "error",
    message,
    correlationId: error.correlationId,
  };
}

function getQueueErrorMessage(error: unknown): string {
  if (!(error instanceof ApiClientError)) {
    return "미배정 상담 목록을 불러오지 못했습니다.";
  }
  if (error.kind === "NETWORK_ERROR" || error.kind === "TIMEOUT") {
    return "네트워크 오류가 발생했습니다. 네트워크 연결을 확인해 주세요.";
  }
  if (error.status === 401) {
    return "로그인이 필요하거나 로그인 정보가 만료되었습니다.";
  }
  if (error.status === 403) {
    return "미배정 상담 목록을 볼 권한이 없습니다.";
  }
  if (error.status === 422) {
    return "미배정 상담 목록의 조회 조건을 확인할 수 없습니다.";
  }
  return "미배정 상담 목록을 불러오지 못했습니다.";
}

function canClaim(inquiry: UnassignedConsultationQueueItemViewModel): boolean {
  return inquiry.allowedActions.some(
    (action) => action.code === "CLAIM_CONSULTATION",
  );
}

export default function UnassignedConsultationQueue({
  dataRepository = consultantWorkspaceDataRepository,
  writeRepository = defaultWriteRepository,
  onClaimed,
}: Props) {
  const [page, setPage] = useState(1);
  const [claimingInquiryId, setClaimingInquiryId] = useState<string | null>(
    null,
  );
  const [feedback, setFeedback] = useState<ClaimFeedback | null>(null);
  const [previewInquiry, setPreviewInquiry] =
    useState<UnassignedConsultationQueueItemViewModel | null>(null);
  const claimingInquiryIdRef = useRef<string | null>(null);
  const queryInput = useMemo(
    () => ({ page, size: PAGE_SIZE, sort: "WAITING_DESC" as const }),
    [page],
  );
  const queueQuery = useUnassignedConsultationQueueQuery(
    queryInput,
    dataRepository,
  );
  const total = queueQuery.data?.pageInfo.total ?? 0;
  const responsePageSize = queueQuery.data?.pageInfo.size ?? PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(total / responsePageSize));

  const refreshQueueAfterClaim = (itemMayBeGone: boolean) => {
    if (
      itemMayBeGone &&
      page > 1 &&
      (queueQuery.data?.items.length ?? 0) <= 1
    ) {
      setPage((current) => Math.max(1, current - 1));
      return;
    }
    queueQuery.retry();
  };

  const handleClaim = async (
    inquiry: UnassignedConsultationQueueItemViewModel,
  ) => {
    if (
      claimingInquiryIdRef.current !== null ||
      !canClaim(inquiry)
    ) {
      return;
    }

    claimingInquiryIdRef.current = inquiry.inquiryId;
    setClaimingInquiryId(inquiry.inquiryId);
    setFeedback(null);

    try {
      if (dataRepository.dataSource === "MOCK") {
        setFeedback({
          inquiryId: inquiry.inquiryId,
          kind: "success",
          message: "상담 시작 화면을 열었습니다.",
        });
        setPreviewInquiry(null);
        onClaimed(inquiry.inquiryId);
        return;
      }

      const response = await writeRepository.claimConsultation(
        inquiry.inquiryId,
        { state_version: inquiry.stateVersion },
        createRequestContext(),
      );
      const result = response.data;
      if (!result || result.inquiry_id !== inquiry.inquiryId) {
        throw new ApiClientError({
          kind: "PARSE_ERROR",
          message: "상담 배정 결과를 확인할 수 없습니다.",
          correlationId: response.metadata.correlation_id,
        });
      }
      setFeedback({
        inquiryId: result.inquiry_id,
        kind: "success",
        message: result.message,
        correlationId: response.metadata.correlation_id,
      });
      refreshQueueAfterClaim(true);
      onClaimed(result.inquiry_id);
    } catch (error) {
      setFeedback(getClaimErrorFeedback(inquiry.inquiryId, error));
      refreshQueueAfterClaim(
        error instanceof ApiClientError &&
          (error.status === 404 || error.status === 409),
      );
    } finally {
      claimingInquiryIdRef.current = null;
      setClaimingInquiryId(null);
    }
  };

  return (
    <section
      className="unassigned-consultation-queue"
      aria-label="미배정 상담 대기 목록"
    >
      <header className="unassigned-consultation-queue__header">
        <div>
          <h2>미배정 상담 대기</h2>
        </div>
        <div className="unassigned-consultation-queue__summary">
          <strong>{total}</strong>
          <span>건 대기</span>
          <button
            type="button"
            onClick={queueQuery.retry}
            disabled={queueQuery.status === "loading"}
          >
            새로고침
          </button>
        </div>
      </header>

      {feedback && (
        <p
          className={`unassigned-consultation-queue__feedback is-${feedback.kind}`}
          role={feedback.kind === "error" ? "alert" : "status"}
        >
          {feedback.message}
          {feedback.correlationId && (
            <small>확인 번호: {feedback.correlationId}</small>
          )}
        </p>
      )}

      <div className="unassigned-consultation-queue__content">
        {queueQuery.status === "loading" ? (
          <p className="unassigned-consultation-queue__state" role="status">
            미배정 상담을 불러오고 있습니다.
          </p>
        ) : queueQuery.status === "error" ? (
          <div className="unassigned-consultation-queue__state" role="alert">
            <span>{getQueueErrorMessage(queueQuery.error)}</span>
            {queueQuery.correlationId && (
              <small>확인 번호: {queueQuery.correlationId}</small>
            )}
            <button type="button" onClick={queueQuery.retry}>
              다시 불러오기
            </button>
          </div>
        ) : queueQuery.data?.items.length ? (
          <div className="unassigned-consultation-queue__items">
            {queueQuery.data.items.map((inquiry) => {
              const isClaiming = claimingInquiryId === inquiry.inquiryId;
              return (
                <article
                  className={`unassigned-consultation-card is-${inquiry.riskLevel}`}
                  key={inquiry.inquiryId}
                  data-testid={`unassigned-consultation-${inquiry.inquiryId}`}
                >
                  <button
                    type="button"
                    className="unassigned-consultation-card__body"
                    aria-label={`${inquiry.symptomSummary} 문의 미리보기`}
                    onClick={() => setPreviewInquiry(inquiry)}
                  >
                    <span className="unassigned-consultation-card__meta">
                      <span className="unassigned-consultation-card__risk">
                        {RISK_LABELS[inquiry.riskLevel]}
                      </span>
                      <span>{formatWaitingTime(inquiry.waitingSeconds)}</span>
                    </span>
                    <strong>{inquiry.symptomSummary}</strong>
                  </button>
                  {canClaim(inquiry) ? (
                    <button
                      className="unassigned-consultation-card__claim"
                      type="button"
                      disabled={claimingInquiryId !== null}
                      aria-label={`${inquiry.symptomSummary} 상담 시작`}
                      onClick={() => void handleClaim(inquiry)}
                    >
                      {isClaiming ? "시작하는 중" : "상담 시작"}
                    </button>
                  ) : (
                    <span className="unassigned-consultation-card__unavailable">
                      현재 배정할 수 없음
                    </span>
                  )}
                </article>
              );
            })}
          </div>
        ) : (
          <p className="unassigned-consultation-queue__state">
            현재 기다리는 미배정 상담이 없습니다.
          </p>
        )}
      </div>

      {queueQuery.status === "success" && (
        <nav
          className="unassigned-consultation-queue__pagination"
          aria-label="미배정 상담 페이지"
        >
          <span className="unassigned-consultation-queue__page-summary">
            총 {total}건 · {page}/{totalPages}페이지
          </span>
          <div className="unassigned-consultation-queue__page-controls">
            <button
              type="button"
              aria-label="미배정 이전 페이지"
              disabled={page <= 1}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
            >
              이전
            </button>
            <button
              type="button"
              aria-label="미배정 다음 페이지"
              disabled={page >= totalPages}
              onClick={() =>
                setPage((current) => Math.min(totalPages, current + 1))
              }
            >
              다음
            </button>
          </div>
        </nav>
      )}

      {previewInquiry && (
        <div className="unassigned-preview-layer">
          <button
            type="button"
            className="unassigned-preview-layer__backdrop"
            aria-label="미배정 문의 미리보기 닫기"
            onClick={() => setPreviewInquiry(null)}
          />
          <section
            className="unassigned-preview"
            role="dialog"
            aria-modal="true"
            aria-labelledby="unassigned-preview-title"
          >
            <header>
              <div>
                <small>미배정 상담 문의</small>
                <h3 id="unassigned-preview-title">
                  {previewInquiry.symptomSummary}
                </h3>
              </div>
              <button
                type="button"
                aria-label="미배정 문의 미리보기 닫기"
                onClick={() => setPreviewInquiry(null)}
              >
                ×
              </button>
            </header>
            <dl>
              <div>
                <dt>긴급도</dt>
                <dd>{RISK_LABELS[previewInquiry.riskLevel]}</dd>
              </div>
              <div>
                <dt>대기 시간</dt>
                <dd>{formatWaitingTime(previewInquiry.waitingSeconds)}</dd>
              </div>
              <div>
                <dt>고객</dt>
                <dd>{previewInquiry.customerDisplayNameMasked}</dd>
              </div>
              <div>
                <dt>제품</dt>
                <dd>{formatProductModelAndName(previewInquiry.productModel)}</dd>
              </div>
            </dl>
            {canClaim(previewInquiry) && (
              <button
                type="button"
                className="unassigned-preview__claim"
                disabled={claimingInquiryId !== null}
                onClick={() => void handleClaim(previewInquiry)}
              >
                {claimingInquiryId === previewInquiry.inquiryId
                  ? "시작하는 중"
                  : "상담 시작"}
              </button>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
