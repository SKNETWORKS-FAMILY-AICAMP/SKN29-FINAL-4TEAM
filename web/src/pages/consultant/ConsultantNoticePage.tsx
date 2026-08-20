import { useEffect, useMemo, useState } from "react";

import EmptyState from "../../common/components/feedback/EmptyState";
import ErrorState from "../../common/components/feedback/ErrorState";
import LoadingState from "../../common/components/feedback/LoadingState";
import ConsultantQueueSidebar from "../../features/consultation/components/ConsultantQueueSidebar";
import ConsultantUserMenu from "../../features/consultation/components/ConsultantUserMenu";
import type { CounselorWorkBucket } from "../../features/consultation/model/consultantWorkspaceTypes";
import { getConsultantNoticePageData } from "../../features/notice/api/consultantNoticeApi";
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

export default function ConsultantNoticePage() {
  const [data, setData] = useState<ConsultantNoticePageData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [categoryFilter, setCategoryFilter] =
    useState<NoticeCategoryFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let active = true;

    getConsultantNoticePageData().then(
      (result) => {
        if (!active) return;
        setData(result);
        setIsLoading(false);
      },
      () => {
        if (!active) return;
        setLoadError(true);
        setIsLoading(false);
      },
    );

    return () => {
      active = false;
    };
  }, [retryCount]);

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

  return (
    <div className="simple-consultant-app consultant-queue-app consultant-notice-app">
      <main className="simple-consultant-main consultant-queue-main">
        <header className="simple-topbar consultant-main-header consultant-unified-header">
          <ConsultantUserMenu className="simple-user" />
        </header>

        <ConsultantQueueSidebar
          activeBucket={null}
          bucketCounts={bucketCounts}
          noticeActive
        />

        <section
          id="consultant-notice-panel"
          className="consultant-notice-panel"
          role="tabpanel"
          aria-labelledby="consultant-notice-title"
        >
          <header className="consultant-notice-head">
            <div>
              <span>NOTICE</span>
              <h1 id="consultant-notice-title">공지사항</h1>
              <p>상담 업무에 필요한 안내와 일정을 확인해 주세요.</p>
            </div>
            <strong>{data?.notices.length ?? 0}건</strong>
          </header>

          <div className="consultant-notice-toolbar">
            <div
              className="consultant-notice-categories"
              aria-label="공지사항 분류"
            >
              {NOTICE_CATEGORY_FILTERS.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  className={categoryFilter === category.id ? "is-active" : ""}
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

          <div className="consultant-notice-content">
            {isLoading ? (
              <LoadingState
                title="공지사항을 불러오고 있습니다."
                description="잠시만 기다려 주세요."
              />
            ) : loadError ? (
              <ErrorState
                title="공지사항을 불러오지 못했습니다."
                description="잠시 후 다시 시도해 주세요."
                onRetry={() => {
                  setIsLoading(true);
                  setLoadError(false);
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
