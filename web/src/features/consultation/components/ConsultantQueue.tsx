import type { ReactNode } from "react";

import type { InquiryId } from "../../../entities/inquiry/inquiryIdentifiers";
import Pagination from "../../../common/components/data-display/Pagination";
import PriorityBadge from "../../../common/components/badge/PriorityBadge";
import RiskBadge from "../../../common/components/badge/RiskBadge";
import StatusBadge from "../../../common/components/badge/StatusBadge";
import {
  formatWaitingTime,
  formatWorkspaceDateTime,
  getPriorityVariant,
  getStatusBadgeVariant,
  PRIORITY_LABELS,
  STATUS_LABELS,
} from "../model/consultantWorkspaceModel";
import type {
  CounselorAssigneeFilter,
  CounselorFilters,
  CounselorInquiry,
  CounselorPriority,
  CounselorRisk,
  CounselorSort,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";
import WorkspaceChip from "./WorkspaceChip";

interface ConsultantQueueProps {
  children: ReactNode;
  filters: CounselorFilters;
  hasChangedConditions: boolean;
  inquiries: readonly CounselorInquiry[];
  page: number;
  selectedInquiryId: InquiryId | null;
  totalItems: number;
  totalPages: number;
  onFiltersChange: (filters: CounselorFilters) => void;
  onPageChange: (page: number) => void;
  onResetFilters: () => void;
  onSelectInquiry: (inquiryId: InquiryId) => void;
}

const FILTERABLE_STATUSES = Object.entries(STATUS_LABELS) as readonly [
  CounselorStatus,
  string,
][];

export default function ConsultantQueue({
  children,
  filters,
  hasChangedConditions,
  inquiries,
  page,
  selectedInquiryId,
  totalItems,
  totalPages,
  onFiltersChange,
  onPageChange,
  onResetFilters,
  onSelectInquiry,
}: ConsultantQueueProps) {
  const updateFilter = <Key extends keyof CounselorFilters>(
    key: Key,
    value: CounselorFilters[Key],
  ) => onFiltersChange({ ...filters, [key]: value });

  return (
    <>
      <section
        id="counselor-queue-filter"
        className="v6-panel v6-filter-panel v6-filter-panel--expanded"
        aria-label="상담 큐 검색과 필터"
      >
        <label className="v6-filter">
          문의 검색
          <input
            type="search"
            value={filters.query}
            onChange={(event) => updateFilter("query", event.target.value)}
            placeholder="문의·시나리오·고객·모델 검색"
          />
        </label>

        <label className="v6-filter">
          상태
          <select
            value={filters.status}
            onChange={(event) =>
              updateFilter(
                "status",
                event.target.value as "ALL" | CounselorStatus,
              )
            }
          >
            <option value="ALL">전체 상태</option>
            {FILTERABLE_STATUSES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="v6-filter">
          위험도
          <select
            value={filters.risk}
            onChange={(event) =>
              updateFilter(
                "risk",
                event.target.value as "ALL" | CounselorRisk,
              )
            }
          >
            <option value="ALL">전체 위험도</option>
            <option value="DANGER">위험</option>
            <option value="CAUTION">주의</option>
            <option value="GENERAL">일반</option>
          </select>
        </label>

        <label className="v6-filter">
          우선순위
          <select
            value={filters.priority}
            onChange={(event) =>
              updateFilter(
                "priority",
                event.target.value as "ALL" | CounselorPriority,
              )
            }
          >
            <option value="ALL">전체 우선순위</option>
            <option value="URGENT">긴급</option>
            <option value="HIGH">높음</option>
            <option value="NORMAL">보통</option>
          </select>
        </label>

        <label className="v6-filter">
          담당자
          <select
            value={filters.assignee}
            onChange={(event) =>
              updateFilter(
                "assignee",
                event.target.value as CounselorAssigneeFilter,
              )
            }
          >
            <option value="ALL">담당·미배정 전체</option>
            <option value="MINE">내 담당 · 한유진</option>
            <option value="UNASSIGNED">미배정</option>
          </select>
        </label>

        <label className="v6-filter">
          업무 우선 조건
          <select
            value={filters.consultation}
            onChange={(event) =>
              updateFilter(
                "consultation",
                event.target.value as CounselorFilters["consultation"],
              )
            }
          >
            <option value="ALL">전체</option>
            <option value="REQUIRED">상담 필수</option>
            <option value="FINAL">최종 완료 대기</option>
          </select>
        </label>

        <label className="v6-filter">
          접수 시작일
          <input
            type="date"
            value={filters.receivedFrom}
            onChange={(event) => updateFilter("receivedFrom", event.target.value)}
          />
        </label>

        <label className="v6-filter">
          접수 종료일
          <input
            type="date"
            value={filters.receivedTo}
            onChange={(event) => updateFilter("receivedTo", event.target.value)}
          />
        </label>

        <label className="v6-filter">
          정렬
          <select
            value={filters.sort}
            onChange={(event) =>
              updateFilter("sort", event.target.value as CounselorSort)
            }
          >
            <option value="UPDATED_DESC">최근 변경 최신순</option>
            <option value="UPDATED_ASC">최근 변경 오래된순</option>
          </select>
        </label>

        <button
          className="v6-button v6-button--secondary v6-filter-reset"
          type="button"
          disabled={!hasChangedConditions}
          onClick={onResetFilters}
        >
          조건 초기화
        </button>

        <span className="v6-filter-summary">
          <b>{totalItems}</b>건
        </span>
      </section>

      <section className="v6-panel v6-queue-layout">
        <aside className="v6-queue-column" aria-label="상담 문의 목록">
          <div className="v6-queue-column__head">
            <strong>우선순위 큐</strong>
            <span>위험·상담·피드백 기준</span>
          </div>

          <div className="v6-queue-list">
            {inquiries.length === 0 ? (
              <div className="v6-empty">
                <span>⌕</span>
                <strong>조건에 맞는 문의가 없습니다.</strong>
                <p>검색어나 필터를 변경해 주세요.</p>
              </div>
            ) : (
              inquiries.map((inquiry) => (
                <button
                  key={inquiry.inquiryId}
                  className={`v6-queue-item${
                    selectedInquiryId === inquiry.inquiryId ? " is-selected" : ""
                  }`}
                  type="button"
                  aria-pressed={selectedInquiryId === inquiry.inquiryId}
                  onClick={() => onSelectInquiry(inquiry.inquiryId)}
                >
                  <span className="v6-queue-item__top">
                    <span className="v6-chip-row">
                      <WorkspaceChip label="합성 시연" tone="info" />
                      <RiskBadge
                        level={inquiry.riskLevel.toLowerCase()}
                        size="compact"
                      />
                      <PriorityBadge
                        label={PRIORITY_LABELS[inquiry.priority]}
                        size="compact"
                        variant={getPriorityVariant(inquiry.priority)}
                      />
                      {inquiry.requiresConsultation && (
                        <WorkspaceChip label="상담 필수" tone="danger" />
                      )}
                      {inquiry.feedbackResolved && (
                        <WorkspaceChip
                          label="해결 피드백 도착"
                          tone="success"
                        />
                      )}
                    </span>
                    <span className="v6-queue-item__wait">
                      대기 {formatWaitingTime(inquiry.waitingMinutes)}
                    </span>
                  </span>

                  <span className="v6-queue-item__symptoms">
                    {inquiry.symptomLabels.map((symptom) => (
                      <span key={symptom}>{symptom}</span>
                    ))}
                  </span>
                  <small>
                    {inquiry.scenarioId} · {inquiry.customerDisplayName} ·{" "}
                    {inquiry.productCode}
                  </small>
                  <span className="v6-queue-item__times">
                    <time dateTime={inquiry.createdAt}>
                      접수 {formatWorkspaceDateTime(inquiry.createdAt)}
                    </time>
                    <time dateTime={inquiry.updatedAt}>
                      변경 {formatWorkspaceDateTime(inquiry.updatedAt)}
                    </time>
                  </span>

                  <span className="v6-queue-item__bottom">
                    <StatusBadge
                      label={STATUS_LABELS[inquiry.status]}
                      size="compact"
                      variant={getStatusBadgeVariant(inquiry.status)}
                    />
                    <b>{inquiry.inquiryCode}</b>
                  </span>
                </button>
              ))
            )}
          </div>

          <Pagination
            page={page}
            totalItems={totalItems}
            totalPages={totalPages}
            onPageChange={onPageChange}
          />
        </aside>

        {children}
      </section>
    </>
  );
}
