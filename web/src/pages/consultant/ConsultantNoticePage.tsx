import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ROUTE_PATHS } from "../../app/router/routePaths";
import { ApiClientError } from "../../common/api/apiError";
import EmptyState from "../../common/components/feedback/EmptyState";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import ConsultantQueueSidebar from "../../features/consultation/components/ConsultantQueueSidebar";
import ConsultantHeaderBrand from "../../features/consultation/components/ConsultantHeaderBrand";
import ConsultantUserMenu from "../../features/consultation/components/ConsultantUserMenu";
import type { CounselorWorkBucket } from "../../features/consultation/model/consultantWorkspaceTypes";
import {
  getConsultantNoticeDetail,
  getConsultantNoticePageData,
} from "../../features/notice/api/consultantNoticeApi";
import {
  CONSULTANT_NOTICE_CATEGORY_LABELS,
  type ConsultantNotice,
  type ConsultantNoticeCategoryCode,
  type ConsultantNoticePageData,
} from "../../features/notice/model/consultantNotice";
import "./ConsultantDashboardPage.css";
import "./ConsultantDashboardTheme.css";
import "./ConsultantInquiryPearlTheme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";
import "../../common/styles/water-glass-theme.css";
import "./ConsultantOperationsTone.css";
import "./ConsultantWorkDashboard.css";
import "./ConsultantNoticePage.css";

type NoticeCategoryFilter = "ALL" | ConsultantNoticeCategoryCode;
type NoticeFailureState =
  | "unauthorized"
  | "forbidden"
  | "server_error"
  | "error";
type NoticePageLoadState = "loading" | "ready" | NoticeFailureState;
type NoticeDetailLoadState =
  | "idle"
  | "loading"
  | "ready"
  | "not_found"
  | NoticeFailureState;

interface NoticeDetailResult {
  requestKey: string;
  notice: ConsultantNotice | null;
  status: Exclude<NoticeDetailLoadState, "idle" | "loading">;
  correlationId: string | null;
}

const NOTICE_CATEGORY_FILTERS: readonly {
  id: NoticeCategoryFilter;
  label: string;
}[] = [
  { id: "ALL", label: "전체" },
  ...Object.entries(CONSULTANT_NOTICE_CATEGORY_LABELS).map(([id, label]) => ({
    id: id as ConsultantNoticeCategoryCode,
    label,
  })),
];

function formatNoticeDate(value: string) {
  return value.replaceAll("-", ".");
}

function matchesQuery(notice: ConsultantNotice, query: string) {
  if (!query) return true;
  return [notice.title, notice.content, notice.department, notice.category]
    .join(" ")
    .toLowerCase()
    .includes(query);
}

function getNoticeFailureState(error: unknown): NoticeFailureState {
  if (!(error instanceof ApiClientError)) return "error";
  if (error.status === 401) return "unauthorized";
  if (error.status === 403) return "forbidden";
  if (error.status !== undefined && error.status >= 500) return "server_error";
  return "error";
}

export default function ConsultantNoticePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<ConsultantNoticePageData | null>(null);
  const [pageLoadState, setPageLoadState] =
    useState<NoticePageLoadState>("loading");
  const [retryCount, setRetryCount] = useState(0);
  const [categoryFilter, setCategoryFilter] =
    useState<NoticeCategoryFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const isDetailRequested = searchParams.has("noticeId");
  const requestedNoticeId = searchParams.get("noticeId") ?? "";
  const [detailRetryCount, setDetailRetryCount] = useState(0);
  const detailRequestKey = isDetailRequested
    ? `${requestedNoticeId}:${detailRetryCount}`
    : "";
  const [detailResult, setDetailResult] = useState<NoticeDetailResult>({
    requestKey: "",
    notice: null,
    status: "error",
    correlationId: null,
  });
  const hasCurrentDetailResult =
    isDetailRequested && detailResult.requestKey === detailRequestKey;
  const selectedNotice = hasCurrentDetailResult ? detailResult.notice : null;
  const detailLoadState: NoticeDetailLoadState = !isDetailRequested
    ? "idle"
    : hasCurrentDetailResult
      ? detailResult.status
      : "loading";
  const detailCorrelationId = hasCurrentDetailResult
    ? detailResult.correlationId
    : null;

  useEffect(() => {
    let active = true;

    getConsultantNoticePageData().then(
      (result) => {
        if (!active) return;
        setData(result);
        setPageLoadState("ready");
      },
      (error: unknown) => {
        if (!active) return;
        setData(null);
        setPageLoadState(getNoticeFailureState(error));
      },
    );

    return () => {
      active = false;
    };
  }, [retryCount]);

  useEffect(() => {
    if (!isDetailRequested) return;

    let active = true;
    const requestKey = detailRequestKey;

    getConsultantNoticeDetail(requestedNoticeId).then(
      (result) => {
        if (!active) return;
        setDetailResult({
          requestKey,
          notice: result,
          status: "ready",
          correlationId: null,
        });
      },
      (error: unknown) => {
        if (!active) return;
        const correlationId =
          error instanceof ApiClientError ? (error.correlationId ?? null) : null;
        if (error instanceof ApiClientError) {
          if (error.status === 404) {
            setDetailResult({
              requestKey,
              notice: null,
              status: "not_found",
              correlationId,
            });
            return;
          }
          if (error.status === 403) {
            setDetailResult({
              requestKey,
              notice: null,
              status: "forbidden",
              correlationId,
            });
            return;
          }
        }
        setDetailResult({
          requestKey,
          notice: null,
          status: getNoticeFailureState(error),
          correlationId,
        });
      },
    );

    return () => {
      active = false;
    };
  }, [detailRequestKey, isDetailRequested, requestedNoticeId]);

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const visibleNotices = useMemo(
    () =>
      [...(data?.notices ?? [])]
        .filter(
          (notice) =>
            (categoryFilter === "ALL" ||
              notice.categoryCode === categoryFilter) &&
            matchesQuery(notice, normalizedQuery),
        )
        .sort((left, right) =>
          right.publishedOn.localeCompare(left.publishedOn),
        ),
    [categoryFilter, data?.notices, normalizedQuery],
  );
  const bucketCounts = useMemo<
    Readonly<Record<CounselorWorkBucket, number>> | undefined
  >(
    () =>
      data
        ? {
            NEW: data.summary.new,
            IN_PROGRESS: data.summary.inProgress,
            COMPLETED: data.summary.completed,
          }
        : undefined,
    [data],
  );

  const returnToNoticeList = () => {
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.delete("noticeId");
    setSearchParams(nextSearchParams);
  };

  return (
    <div className="simple-consultant-app consultant-queue-app consultant-notice-app">
      <main className="simple-consultant-main consultant-queue-main">
        <header className="simple-topbar consultant-main-header consultant-unified-header">
          <ConsultantHeaderBrand />
          <ConsultantUserMenu className="simple-user" />
        </header>

        <ConsultantQueueSidebar
          activeBucket={null}
          bucketCounts={bucketCounts}
          noticeActive
        />

        <section
          id="consultant-notice-panel"
          className={`consultant-notice-panel${isDetailRequested ? " is-detail" : ""}`}
          role="tabpanel"
          aria-labelledby="consultant-notice-title"
        >
          <header className="consultant-notice-head">
            <div>
              <span>NOTICE</span>
              <h1 id="consultant-notice-title">
                {isDetailRequested ? "공지사항 상세" : "공지사항"}
              </h1>
              <p>
                {isDetailRequested
                  ? "선택한 공지의 내용을 자세히 확인해 주세요."
                  : "상담 업무에 필요한 안내와 일정을 확인해 주세요."}
              </p>
            </div>
            <strong>
              {isDetailRequested ? "상세" : `${data?.notices.length ?? 0}건`}
            </strong>
          </header>

          {!isDetailRequested && (
            <div className="consultant-notice-toolbar">
              <div
                className="consultant-notice-categories"
                aria-label="공지사항 분류"
              >
                {NOTICE_CATEGORY_FILTERS.map((category) => (
                  <button
                    key={category.id}
                    type="button"
                    className={
                      categoryFilter === category.id ? "is-active" : ""
                    }
                    aria-pressed={categoryFilter === category.id}
                    onClick={() => setCategoryFilter(category.id)}
                  >
                    {category.label}
                  </button>
                ))}
              </div>

              <label className="consultant-notice-search">
                <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24">
                  <circle cx="10.5" cy="10.5" r="6.25" />
                  <path d="m15.25 15.25 4.5 4.5" />
                </svg>
                <span className="consultant-visually-hidden">공지사항 검색</span>
                <input
                  type="search"
                  value={searchQuery}
                  placeholder="제목, 내용, 부서 검색"
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
              </label>
            </div>
          )}

          <div className="consultant-notice-content">
            {isDetailRequested &&
            (detailLoadState === "idle" || detailLoadState === "loading") ? (
              <LoadingState
                title="공지사항 상세를 불러오고 있습니다."
                description="선택한 공지 내용을 확인하고 있습니다."
              />
            ) : isDetailRequested && detailLoadState === "forbidden" ? (
              <ForbiddenState
                title="이 공지사항을 볼 권한이 없습니다."
                description={
                  detailCorrelationId
                    ? `상담사 권한을 확인해 주세요. 확인 번호: ${detailCorrelationId}`
                    : "상담사 권한을 확인해 주세요."
                }
                actionLabel="공지사항 목록으로"
                onAction={returnToNoticeList}
              />
            ) : isDetailRequested && detailLoadState === "unauthorized" ? (
              <ForbiddenState
                title="로그인이 만료되어 공지사항을 볼 수 없습니다."
                description="다시 로그인한 뒤 공지사항을 확인해 주세요."
                actionLabel="로그인 화면으로"
                onAction={() => navigate(ROUTE_PATHS.login)}
              />
            ) : isDetailRequested && detailLoadState === "not_found" ? (
              <EmptyState
                title="해당 공지사항을 찾을 수 없습니다."
                description="게시되지 않았거나 삭제된 공지사항일 수 있습니다."
                actionLabel="공지사항 목록으로"
                onAction={returnToNoticeList}
              />
            ) : isDetailRequested && detailLoadState === "server_error" ? (
              <ErrorState
                title="공지사항 서버에 일시적인 오류가 발생했습니다."
                description={
                  detailCorrelationId
                    ? `잠시 후 다시 시도해 주세요. 확인 번호: ${detailCorrelationId}`
                    : "잠시 후 다시 시도해 주세요."
                }
                onRetry={() => {
                  setDetailRetryCount((count) => count + 1);
                }}
              />
            ) : isDetailRequested && detailLoadState === "error" ? (
              <ErrorState
                title="공지사항 상세를 불러오지 못했습니다."
                description={
                  detailCorrelationId
                    ? `잠시 후 다시 시도해 주세요. 확인 번호: ${detailCorrelationId}`
                    : "잠시 후 다시 시도해 주세요."
                }
                onRetry={() => {
                  setDetailRetryCount((count) => count + 1);
                }}
              />
            ) : isDetailRequested ? (
              selectedNotice ? (
                <article
                  className="consultant-notice-detail"
                  aria-labelledby="consultant-notice-detail-title"
                >
                  <button
                    type="button"
                    className="consultant-notice-detail__back"
                    onClick={returnToNoticeList}
                  >
                    <span aria-hidden="true">←</span>
                    공지사항 목록으로
                  </button>

                  <header className="consultant-notice-detail__head">
                    <div className="consultant-notice-detail__eyebrow">
                      <em data-category={selectedNotice.category}>
                        {selectedNotice.category}
                      </em>
                      <span>{selectedNotice.noticeCode}</span>
                    </div>
                    <h2 id="consultant-notice-detail-title">
                      {selectedNotice.title}
                    </h2>
                    <div className="consultant-notice-detail__meta">
                      <span>{selectedNotice.department}</span>
                      <time dateTime={selectedNotice.publishedOn}>
                        {formatNoticeDate(selectedNotice.publishedOn)}
                      </time>
                    </div>
                  </header>

                  <div className="consultant-notice-detail__body">
                    <p>{selectedNotice.content}</p>
                  </div>
                </article>
              ) : null
            ) : pageLoadState === "loading" ? (
              <LoadingState
                title="공지사항을 불러오고 있습니다."
                description="잠시만 기다려 주세요."
              />
            ) : pageLoadState === "unauthorized" ? (
              <ForbiddenState
                title="로그인이 만료되어 공지사항을 불러올 수 없습니다."
                description="다시 로그인한 뒤 공지사항을 확인해 주세요."
                actionLabel="로그인 화면으로"
                onAction={() => navigate(ROUTE_PATHS.login)}
              />
            ) : pageLoadState === "forbidden" ? (
              <ForbiddenState
                title="공지사항을 볼 권한이 없습니다."
                description="상담사 계정과 활성 상태를 확인해 주세요."
              />
            ) : pageLoadState === "server_error" ? (
              <ErrorState
                title="공지사항 서버에 일시적인 오류가 발생했습니다."
                description="잠시 후 다시 시도해 주세요."
                onRetry={() => {
                  setPageLoadState("loading");
                  setRetryCount((count) => count + 1);
                }}
              />
            ) : pageLoadState === "error" ? (
              <ErrorState
                title="공지사항을 불러오지 못했습니다."
                description="네트워크 연결을 확인한 뒤 다시 시도해 주세요."
                onRetry={() => {
                  setPageLoadState("loading");
                  setRetryCount((count) => count + 1);
                }}
              />
            ) : visibleNotices.length === 0 ? (
              <EmptyState
                title="조건에 맞는 공지사항이 없습니다."
                description="분류를 바꾸거나 다른 검색어를 입력해 주세요."
              />
            ) : (
              <ul className="consultant-notice-list">
                {visibleNotices.map((notice) => (
                  <li key={notice.noticeId}>
                    <article>
                      <div className="consultant-notice-list__main">
                        <em data-category={notice.category}>{notice.category}</em>
                        <div>
                          <h2>{notice.title}</h2>
                          <p>{notice.content}</p>
                        </div>
                      </div>
                      <div className="consultant-notice-list__meta">
                        <span>{notice.department}</span>
                        <time dateTime={notice.publishedOn}>
                          {formatNoticeDate(notice.publishedOn)}
                        </time>
                      </div>
                    </article>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
