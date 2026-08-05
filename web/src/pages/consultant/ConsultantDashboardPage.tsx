import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createInquiryDetailPath } from "../../app/router/routePaths";
import { useAuth } from "../../app/providers/authContext";
import RiskBadge from "../../common/components/badge/RiskBadge";
import StatusBadge from "../../common/components/badge/StatusBadge";
import Pagination from "../../common/components/data-display/Pagination";
import EmptyState from "../../common/components/feedback/EmptyState";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import type { InquiryId } from "../../entities/inquiry/inquiryIdentifiers";
import CompactConsultationDesk from "../../features/consultation/components/CompactConsultationDesk";
import useCounselorQueueFilters from "../../features/consultation/hooks/useCounselorQueueFilters";
import {
  formatWaitingTime,
  getCounselorQueuePage,
  getCounselorWorkBucket,
  getStatusBadgeVariant,
  STATUS_LABELS,
  WORK_BUCKET_LABELS,
} from "../../features/consultation/model/consultantWorkspaceModel";
import type {
  CounselorAllowedAction,
  CounselorStatus,
  CounselorWorkBucket,
} from "../../features/consultation/model/consultantWorkspaceTypes";
import { consultantWorkspaceRepository } from "../../features/consultation/repositories/consultantWorkspaceRepository";
import ApiRuntimeStatus from "../../features/runtime-status/components/ApiRuntimeStatus";
import "./ConsultantDashboardPage.css";
import "./ConsultantDashboardTheme.css";
import "./ConsultantInquiryPearlTheme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";

const WORK_BUCKETS: readonly {
  id: CounselorWorkBucket;
  description: string;
}[] = [
  {
    id: "NEW",
    description: "",
  },
  {
    id: "IN_PROGRESS",
    description: "상담·기사 배정·일정 조율 중인 문의",
  },
  {
    id: "COMPLETED",
    description: "최종 완료 또는 취소된 문의",
  },
];

export default function ConsultantDashboardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { filters, hasChangedConditions, resetFilters, setFilters } =
    useCounselorQueueFilters();
  const isQueryComposingRef = useRef(false);
  const [queryInput, setQueryInput] = useState(filters.query);
  const [activeBucket, setActiveBucket] =
    useState<CounselorWorkBucket>("NEW");
  const [selectedInquiryId, setSelectedInquiryId] =
    useState<InquiryId | null>(null);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [inquiryStateUpdates, setInquiryStateUpdates] = useState<
    Record<
      string,
      {
        status: CounselorStatus;
        stateVersion: number;
        allowedActions: readonly CounselorAllowedAction[];
      }
    >
  >({});

  const mockState = new URLSearchParams(location.search).get("mockState");
  const loadState = ["loading", "error", "forbidden"].includes(
    mockState ?? "",
  )
    ? (mockState as "loading" | "error" | "forbidden")
    : "ready";
  const sourceInquiries = useMemo(
    () =>
      mockState === "empty"
        ? []
        : consultantWorkspaceRepository.listConsultantQueue().map((inquiry) => ({
            ...inquiry,
            ...inquiryStateUpdates[inquiry.inquiryId],
          })),
    [inquiryStateUpdates, mockState],
  );

  useEffect(() => {
    if (!isQueryComposingRef.current) {
      setQueryInput(filters.query);
    }
  }, [filters.query]);

  useEffect(() => {
    document.body.classList.add("compact-consultant-body");
    return () => document.body.classList.remove("compact-consultant-body");
  }, []);

  useEffect(() => {
    if (!selectedInquiryId) return;

    document.body.classList.add("consultant-detail-open");
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedInquiryId(null);
    };
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.classList.remove("consultant-detail-open");
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [selectedInquiryId]);

  const bucketCounts = useMemo(
    () =>
      sourceInquiries.reduce<Record<CounselorWorkBucket, number>>(
        (counts, inquiry) => {
          counts[getCounselorWorkBucket(inquiry.status)] += 1;
          return counts;
        },
        { NEW: 0, IN_PROGRESS: 0, COMPLETED: 0 },
      ),
    [sourceInquiries],
  );
  const bucketInquiries = useMemo(
    () =>
      sourceInquiries.filter(
        (inquiry) => getCounselorWorkBucket(inquiry.status) === activeBucket,
      ),
    [activeBucket, sourceInquiries],
  );
  const queuePage = useMemo(
    () => getCounselorQueuePage(bucketInquiries, filters),
    [bucketInquiries, filters],
  );
  const selectedInquiry =
    sourceInquiries.find((item) => item.inquiryId === selectedInquiryId) ?? null;
  const activeBucketCopy = WORK_BUCKETS.find(
    (bucket) => bucket.id === activeBucket,
  );

  const changeBucket = (bucket: CounselorWorkBucket) => {
    setActiveBucket(bucket);
    setSelectedInquiryId(null);
    if (filters.page !== 1) setFilters({ ...filters, page: 1 });
  };

  const advanceToNextInquiry = () => {
    if (!selectedInquiry || queuePage.items.length < 2) {
      setSelectedInquiryId(null);
      return;
    }

    const currentIndex = queuePage.items.findIndex(
      (item) => item.inquiryId === selectedInquiry.inquiryId,
    );
    const nextInquiry =
      currentIndex < 0
        ? queuePage.items[0]
        : queuePage.items[currentIndex + 1] ?? queuePage.items[0];
    setSelectedInquiryId(nextInquiry.inquiryId);
  };

  return (
    <div className="simple-consultant-app consultant-queue-app">
      <header className="simple-topbar">
        <a className="simple-brand" href="/" aria-label="Water Bridge 홈으로 이동">
          <span className="simple-brand__mark" aria-hidden="true">W</span>
          <div className="simple-brand__copy">
            <strong>Water Bridge</strong>
            <small>상담 워크스페이스</small>
          </div>
        </a>

        <ApiRuntimeStatus className="simple-topbar__notice" compact />

        <div className="simple-user">
          <span className="simple-user__avatar">{user?.displayName.slice(0, 1) ?? "상"}</span>
          <div className="simple-user__copy">
            <strong>{user?.displayName ?? "상담사"}</strong>
            <small>상담사 · 업무 중</small>
          </div>
        </div>
      </header>

      <main className="simple-consultant-main consultant-queue-main">
        <h1 id="simple-page-title" className="consultant-visually-hidden">
          고객 문의
        </h1>

        <nav className="consultant-work-tabs" aria-label="문의 처리 상태" role="tablist">
          {WORK_BUCKETS.map((bucket) => (
            <button
              key={bucket.id}
              type="button"
              role="tab"
              aria-selected={activeBucket === bucket.id}
              aria-controls="consultant-queue-panel"
              className={`consultant-work-tab consultant-work-tab--${bucket.id.toLowerCase()}${
                activeBucket === bucket.id ? " is-active" : ""
              }`}
              onClick={() => changeBucket(bucket.id)}
            >
              <span>
                <strong>{WORK_BUCKET_LABELS[bucket.id]}</strong>
                {bucket.description && <em>{bucket.description}</em>}
              </span>
              <b>{bucketCounts[bucket.id]}</b>
            </button>
          ))}
        </nav>

        <section
          id="consultant-queue-panel"
          className="consultant-queue-panel"
          role="tabpanel"
          aria-label={WORK_BUCKET_LABELS[activeBucket]}
        >
          <header className="consultant-queue-panel__head">
            <div>
              <small className="consultant-queue-panel__eyebrow">COUNSEL QUEUE</small>
              <h2>{WORK_BUCKET_LABELS[activeBucket]}</h2>
              {activeBucketCopy?.description && <p>{activeBucketCopy.description}</p>}
            </div>

            <div className="consultant-queue-tools">
              <label className="simple-search">
                <span aria-hidden="true">⌕</span>
                <input
                  type="search"
                  aria-label="문의 검색"
                  value={queryInput}
                  onCompositionStart={() => {
                    isQueryComposingRef.current = true;
                  }}
                  onCompositionEnd={(event) => {
                    isQueryComposingRef.current = false;
                    const query = event.currentTarget.value;
                    setQueryInput(query);
                    setFilters({ ...filters, query, page: 1 });
                  }}
                  onChange={(event) => {
                    const query = event.target.value;
                    setQueryInput(query);
                    if (!isQueryComposingRef.current) {
                      setFilters({ ...filters, query, page: 1 });
                    }
                  }}
                  placeholder="고객명, 증상, 문의번호 검색"
                />
              </label>
              {hasChangedConditions && (
                <button type="button" onClick={resetFilters}>
                  검색 초기화
                </button>
              )}
            </div>
          </header>

          <div className="consultant-list" aria-label="상담 문의 목록">
            {loadState === "loading" ? (
              <LoadingState
                title="상담 문의 목록을 불러오고 있습니다."
                description="잠시만 기다려 주세요."
              />
            ) : loadState === "error" ? (
              <ErrorState
                title="상담 문의 목록을 불러오지 못했습니다."
                description="잠시 후 다시 시도해 주세요."
                onRetry={() => navigate("/consultant/inquiries", { replace: true })}
              />
            ) : loadState === "forbidden" ? (
              <ForbiddenState
                title="상담 문의 목록을 볼 권한이 없습니다."
                description="상담사 역할과 담당 범위를 확인해 주세요."
              />
            ) : queuePage.items.length === 0 ? (
              <EmptyState
                title={
                  hasChangedConditions
                    ? "검색 조건에 맞는 문의가 없습니다."
                    : `${WORK_BUCKET_LABELS[activeBucket]}가 없습니다.`
                }
                description={
                  hasChangedConditions
                    ? "검색어를 바꾸거나 초기화해 주세요."
                    : activeBucket === "NEW"
                      ? "새 문의가 들어오면 여기에 바로 표시됩니다."
                      : "현재 해당 상태의 문의가 없습니다."
                }
                actionLabel={hasChangedConditions ? "검색 초기화" : undefined}
                onAction={hasChangedConditions ? resetFilters : undefined}
              />
            ) : (
              queuePage.items.map((inquiry) => (
                <button
                  key={inquiry.inquiryId}
                  className="v6-queue-item consultant-list-item"
                  type="button"
                  aria-label={`${inquiry.inquiryCode} ${inquiry.customerDisplayName} ${inquiry.symptomLabel} 상세 열기`}
                  onClick={() => setSelectedInquiryId(inquiry.inquiryId)}
                >
                  <span className="consultant-list-item__risk">
                    <RiskBadge
                      level={inquiry.riskLevel.toLowerCase()}
                      size="compact"
                    />
                    <em>
                      {activeBucket === "COMPLETED"
                        ? "처리 기록"
                        : `대기 ${formatWaitingTime(inquiry.waitingMinutes)}`}
                    </em>
                  </span>

                  <span className="consultant-list-item__subject">
                    <strong>{inquiry.symptomLabel}</strong>
                    <small>{inquiry.customerMessage}</small>
                  </span>

                  <span className="consultant-list-item__customer">
                    <strong>{inquiry.customerDisplayName}</strong>
                    <small>{inquiry.productCode}</small>
                  </span>

                  <span className="consultant-list-item__status">
                    <StatusBadge
                      label={STATUS_LABELS[inquiry.status]}
                      size="compact"
                      variant={getStatusBadgeVariant(inquiry.status)}
                    />
                    <small>{inquiry.inquiryCode}</small>
                  </span>

                  <span className="consultant-list-item__open" aria-hidden="true">
                    상세 보기 <b>›</b>
                  </span>
                </button>
              ))
            )}
          </div>

          {loadState === "ready" && queuePage.totalItems > 0 && (
            <Pagination
              page={queuePage.currentPage}
              totalItems={queuePage.totalItems}
              totalPages={queuePage.totalPages}
              onPageChange={(page) => setFilters({ ...filters, page })}
            />
          )}
        </section>
      </main>

      {selectedInquiry && (
        <div className="consultant-detail-layer">
          <button
            type="button"
            className="consultant-detail-backdrop"
            aria-label="문의 상세 닫기"
            onClick={() => setSelectedInquiryId(null)}
          />
          <section
            className="consultant-detail-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="consultant-detail-title"
          >
            <header className="consultant-detail-drawer__head">
              <div>
                <small>{selectedInquiry.inquiryCode}</small>
                <h2 id="consultant-detail-title">
                  {selectedInquiry.customerDisplayName} · {selectedInquiry.symptomLabel}
                </h2>
                <p>선택한 문의의 상담과 기사 일정을 여기에서 처리합니다.</p>
              </div>
              <button
                type="button"
                aria-label="문의 상세 닫기"
                onClick={() => setSelectedInquiryId(null)}
              >
                <span aria-hidden="true">×</span>
              </button>
            </header>

            <div className="consultant-detail-drawer__body">
              <CompactConsultationDesk
                key={selectedInquiry.inquiryId}
                inquiry={selectedInquiry}
                autoAdvance={autoAdvance}
                onAutoAdvanceChange={setAutoAdvance}
                onAdvanceToNext={advanceToNextInquiry}
                onInquiryStateChange={(update) => {
                  setInquiryStateUpdates((current) => ({
                    ...current,
                    [selectedInquiry.inquiryId]: update,
                  }));
                  setActiveBucket(getCounselorWorkBucket(update.status));
                }}
                onOpenFullDetail={() =>
                  navigate(createInquiryDetailPath(selectedInquiry.inquiryId), {
                    state: { returnTo: `/consultant/inquiries${location.search}` },
                  })
                }
              />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
