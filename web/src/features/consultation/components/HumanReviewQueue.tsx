import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiClientError } from "../../../common/api/apiError";
import { IdempotencyOperationTracker } from "../../../common/api/idempotencyOperation";
import { createRequestContext } from "../../../common/api/requestContext";
import type {
  HumanReviewDecisionRequestDto,
  HumanReviewDto,
} from "../api/humanReviewRemoteTypes";
import {
  createRemoteConsultationWriteRepository,
  type ConsultationWriteRepository,
} from "../repositories/consultationWriteRepository";
import {
  humanReviewRepository,
  type HumanReviewRepository,
} from "../repositories/humanReviewRepository";
import "./HumanReviewQueue.css";

type LoadStatus = "loading" | "success" | "error";

interface PendingClaim {
  review: HumanReviewDto;
}

interface Feedback {
  kind: "error" | "success";
  message: string;
  correlationId?: string;
}

interface Props {
  reviewRepository?: HumanReviewRepository;
  writeRepository?: ConsultationWriteRepository;
  onClaimed: (inquiryId: string) => void;
}

const defaultWriteRepository = createRemoteConsultationWriteRepository();

function requireReviewData(
  data: HumanReviewDto | null,
  expectedReviewId: string,
  correlationId: string,
): HumanReviewDto {
  if (!data || data.review_id !== expectedReviewId) {
    throw new ApiClientError({
      kind: "PARSE_ERROR",
      message: "AI 검수 결과를 확인할 수 없습니다.",
      correlationId,
    });
  }
  return data;
}

function isRetryable(error: unknown): boolean {
  return (
    !(error instanceof ApiClientError) ||
    error.kind === "NETWORK_ERROR" ||
    error.kind === "TIMEOUT" ||
    error.kind === "SERVER_ERROR"
  );
}

function errorFeedback(error: unknown, approved: boolean): Feedback {
  if (!(error instanceof ApiClientError)) {
    return {
      kind: "error",
      message: approved
        ? "검수는 승인되었지만 상담 배정에 실패했습니다. 다시 시도해 주세요."
        : "AI 검수를 처리하지 못했습니다. 다시 시도해 주세요.",
    };
  }

  let message = approved
    ? "검수는 승인되었지만 상담 배정에 실패했습니다. 다시 시도해 주세요."
    : "AI 검수를 처리하지 못했습니다. 다시 시도해 주세요.";
  if (error.status === 401) {
    message = "로그인이 만료되었습니다. 다시 로그인해 주세요.";
  } else if (error.status === 403) {
    message = "이 검수 또는 상담을 처리할 권한이 없습니다.";
  } else if (error.status === 404 || error.status === 409) {
    message = "다른 작업자가 먼저 처리했거나 문의 상태가 변경되었습니다. 목록을 새로고침해 주세요.";
  } else if (error.status === 422) {
    message = "검수 요청 정보를 확인할 수 없습니다. 목록을 새로고침해 주세요.";
  }
  return { kind: "error", message, correlationId: error.correlationId };
}

function buildDecision(review: HumanReviewDto): HumanReviewDecisionRequestDto {
  if (review.original_requires_consultation) {
    return {
      decision: "APPROVE",
      review_state_version: review.review_state_version,
      reason_code: "APPROVED_AS_IS",
      consultation_disposition: "PRESERVE",
    };
  }
  return {
    decision: "APPROVE",
    review_state_version: review.review_state_version,
    reason_code: "APPROVED_AS_IS",
    consultation_disposition: "REQUIRE",
    consultation_reason_code: "PRODUCT_FUNCTION_UNCERTAIN",
  };
}

export default function HumanReviewQueue({
  reviewRepository = humanReviewRepository,
  writeRepository = defaultWriteRepository,
  onClaimed,
}: Props) {
  const [loadStatus, setLoadStatus] = useState<LoadStatus>("loading");
  const [reviews, setReviews] = useState<HumanReviewDto[]>([]);
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);
  const [busyReviewId, setBusyReviewId] = useState<string | null>(null);
  const [pendingClaim, setPendingClaim] = useState<PendingClaim | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const mutationLock = useRef(false);
  const decisionTrackers = useRef(new Map<string, IdempotencyOperationTracker>());
  const claimTrackers = useRef(new Map<string, IdempotencyOperationTracker>());

  const retry = useCallback(() => {
    setLoadStatus("loading");
    setFeedback(null);
    setRetryCount((count) => count + 1);
  }, []);

  useEffect(() => {
    let active = true;
    reviewRepository.list().then(
      (response) => {
        if (!active) return;
        const items = response.data?.items;
        if (!Array.isArray(items)) {
          setReviews([]);
          setFeedback({
            kind: "error",
            message: "AI 검수 목록 응답을 확인할 수 없습니다.",
            correlationId: response.metadata.correlation_id,
          });
          setLoadStatus("error");
          return;
        }
        setReviews(items);
        setActiveReviewId((current) =>
          items.some((review) => review.review_id === current)
            ? current
            : (items[0]?.review_id ?? null),
        );
        setLoadStatus("success");
      },
      (error: unknown) => {
        if (!active) return;
        setReviews([]);
        setFeedback(errorFeedback(error, false));
        setLoadStatus("error");
      },
    );
    return () => {
      active = false;
    };
  }, [reviewRepository, retryCount]);

  const activeReview = useMemo(
    () =>
      reviews.find((review) => review.review_id === activeReviewId) ??
      reviews[0] ??
      null,
    [activeReviewId, reviews],
  );

  const trackerFor = (
    store: Map<string, IdempotencyOperationTracker>,
    id: string,
  ) => {
    const current = store.get(id);
    if (current) return current;
    const tracker = new IdempotencyOperationTracker();
    store.set(id, tracker);
    return tracker;
  };

  const claimApprovedReview = async (approvedReview: HumanReviewDto) => {
    if (
      approvedReview.inquiry_status !== "CONSULTATION_REQUIRED" ||
      approvedReview.inquiry_state_version < 1
    ) {
      throw new ApiClientError({
        kind: "PARSE_ERROR",
        message: "상담 전환 상태를 확인할 수 없습니다.",
      });
    }
    const tracker = trackerFor(claimTrackers.current, approvedReview.inquiry_id);
    const signature = `${approvedReview.inquiry_id}:${approvedReview.inquiry_state_version}`;
    const key = tracker.begin(signature);
    try {
      const response = await writeRepository.claimConsultation(
        approvedReview.inquiry_id,
        { state_version: approvedReview.inquiry_state_version },
        createRequestContext({ idempotencyKey: key }),
      );
      if (!response.data || response.data.inquiry_id !== approvedReview.inquiry_id) {
        throw new ApiClientError({
          kind: "PARSE_ERROR",
          message: "상담 배정 결과를 확인할 수 없습니다.",
          correlationId: response.metadata.correlation_id,
        });
      }
      tracker.finish();
      return response.data.inquiry_id;
    } catch (error) {
      tracker.fail(isRetryable(error));
      throw error;
    }
  };

  const handleApproveAndClaim = async (review: HumanReviewDto) => {
    if (mutationLock.current) return;
    mutationLock.current = true;
    setBusyReviewId(review.review_id);
    setFeedback(null);
    let approvedReview =
      pendingClaim?.review.review_id === review.review_id
        ? pendingClaim.review
        : null;

    try {
      if (!approvedReview) {
        const body = buildDecision(review);
        const tracker = trackerFor(decisionTrackers.current, review.review_id);
        const signature = `${review.review_id}:${JSON.stringify(body)}`;
        const key = tracker.begin(signature);
        try {
          const response = await reviewRepository.decide(
            review.review_id,
            body,
            createRequestContext({ idempotencyKey: key }),
          );
          approvedReview = requireReviewData(
            response.data,
            review.review_id,
            response.metadata.correlation_id,
          );
          tracker.finish();
          setPendingClaim({ review: approvedReview });
        } catch (error) {
          tracker.fail(isRetryable(error));
          throw error;
        }
      }

      const inquiryId = await claimApprovedReview(approvedReview);
      setPendingClaim(null);
      setFeedback({
        kind: "success",
        message: "AI 검수를 승인하고 상담을 내 문의로 배정했습니다.",
      });
      setReviews((current) =>
        current.filter((item) => item.review_id !== review.review_id),
      );
      onClaimed(inquiryId);
      retry();
    } catch (error) {
      const decisionWasApproved = approvedReview !== null;
      setFeedback(errorFeedback(error, decisionWasApproved));
      if (
        error instanceof ApiClientError &&
        (error.status === 404 || error.status === 409)
      ) {
        setPendingClaim(null);
        retry();
      }
    } finally {
      mutationLock.current = false;
      setBusyReviewId(null);
    }
  };

  const isResumingClaim =
    activeReview !== null &&
    pendingClaim?.review.review_id === activeReview.review_id;

  return (
    <aside className="counselor-ai-review" aria-labelledby="counselor-ai-review-title">
      <header className="counselor-ai-review__header">
        <div>
          <span>AI QUALITY CHECK</span>
          <h2 id="counselor-ai-review-title">AI 요약 검수</h2>
        </div>
        <b aria-label={`${reviews.length}건 대기`}>{reviews.length}</b>
      </header>

      {feedback && (
        <p
          className={`counselor-ai-review__feedback is-${feedback.kind}`}
          role={feedback.kind === "error" ? "alert" : "status"}
        >
          {feedback.message}
          {feedback.correlationId && <small>확인 번호: {feedback.correlationId}</small>}
        </p>
      )}

      {loadStatus === "loading" ? (
        <div className="counselor-ai-review__empty" role="status">
          <span aria-hidden="true">…</span>
          <strong>AI 검수 목록을 불러오고 있습니다.</strong>
        </div>
      ) : loadStatus === "error" ? (
        <div className="counselor-ai-review__empty">
          <span aria-hidden="true">!</span>
          <strong>AI 검수 목록을 불러오지 못했습니다.</strong>
          <button type="button" onClick={retry}>다시 불러오기</button>
        </div>
      ) : !activeReview ? (
        <div className="counselor-ai-review__empty">
          <span aria-hidden="true">✓</span>
          <strong>대기 중인 AI 검수가 없습니다.</strong>
          <p>새 문진 결과가 도착하면 이 영역에 표시됩니다.</p>
        </div>
      ) : (
        <>
          <p className="counselor-ai-review__notice">
            고객에게 안내되기 전 AI 결과와 상담 필요 여부를 확인해 주세요.
          </p>
          <section className="counselor-ai-review__case">
            <div>
              <span>{activeReview.model_code}</span>
              <span>{activeReview.reason_code}</span>
            </div>
            <strong>{activeReview.proposed_guidance.title}</strong>
            <p>{activeReview.proposed_guidance.summary_text}</p>
          </section>
          <div className="counselor-ai-compare">
            <article>
              <header><span>AI</span><strong>고객 안내 초안</strong></header>
              <blockquote>{activeReview.proposed_guidance.summary_text}</blockquote>
            </article>
            <article>
              <header><span>확인</span><strong>안전 안내 및 다음 조치</strong></header>
              {activeReview.proposed_guidance.safety_notice && (
                <p className="counselor-ai-review__safety">
                  {activeReview.proposed_guidance.safety_notice}
                </p>
              )}
              <ol className="counselor-ai-review__items">
                {activeReview.proposed_guidance.items.map((item) => (
                  <li key={`${activeReview.review_id}-${item.step_no}`}>
                    {item.instruction_text}
                  </li>
                ))}
              </ol>
              <div className="counselor-ai-review__integration">
                <strong>상담 연결</strong>
                <p>
                  승인하면 이 문의를 상담 필요 상태로 전환한 뒤 현재 상담사에게 배정합니다.
                </p>
              </div>
            </article>
          </div>
          <div className="counselor-ai-review__actions is-single">
            <button
              type="button"
              className="is-primary"
              disabled={busyReviewId !== null}
              onClick={() => void handleApproveAndClaim(activeReview)}
            >
              {busyReviewId === activeReview.review_id
                ? "처리하는 중"
                : isResumingClaim
                  ? "상담 배정 다시 시도"
                  : "검수 승인 후 상담 시작"}
            </button>
          </div>
          {reviews.length > 1 && (
            <nav className="counselor-ai-review__queue" aria-label="AI 검수 대기 목록">
              <span>검수 대기</span>
              {reviews.map((review, index) => (
                <button
                  key={review.review_id}
                  type="button"
                  className={review.review_id === activeReview.review_id ? "is-active" : ""}
                  aria-pressed={review.review_id === activeReview.review_id}
                  onClick={() => setActiveReviewId(review.review_id)}
                >
                  {index + 1}. {review.model_code}
                </button>
              ))}
            </nav>
          )}
        </>
      )}
    </aside>
  );
}
