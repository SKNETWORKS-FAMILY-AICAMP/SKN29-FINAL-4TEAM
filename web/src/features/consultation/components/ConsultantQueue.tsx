import type { ReactNode } from "react";

import {
  formatWorkspaceDateTime,
  getRiskTone,
  getStatusTone,
  RISK_LABELS,
  STATUS_LABELS,
} from "../model/consultantWorkspaceModel";
import type {
  CounselorFilters,
  CounselorInquiry,
  CounselorRisk,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";
import WorkspaceChip from "./WorkspaceChip";

interface ConsultantQueueProps {
  children: ReactNode;
  filters: CounselorFilters;
  inquiries: readonly CounselorInquiry[];
  selectedInquiryId: string | null;
  onFiltersChange: (filters: CounselorFilters) => void;
  onSelectInquiry: (inquiryId: string) => void;
}

export default function ConsultantQueue({
  children,
  filters,
  inquiries,
  selectedInquiryId,
  onFiltersChange,
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
        className="v6-panel v6-filter-panel"
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
            <option value="COMPLETION_PENDING">최종 완료 대기</option>
            <option value="VISIT_SCHEDULED">방문 예정</option>
            <option value="CONSULTATION_IN_PROGRESS">상담 진행 중</option>
            <option value="CONSULTATION_REQUIRED">상담 대기</option>
            <option value="QUESTIONNAIRE_IN_PROGRESS">문진 진행 중</option>
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

        <span className="v6-filter-summary">
          <b>{inquiries.length}</b>건
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
                  key={inquiry.id}
                  className={`v6-queue-item${
                    selectedInquiryId === inquiry.id ? " is-selected" : ""
                  }`}
                  type="button"
                  aria-pressed={selectedInquiryId === inquiry.id}
                  onClick={() => onSelectInquiry(inquiry.id)}
                >
                  <span className="v6-queue-item__top">
                    <span className="v6-chip-row">
                      <WorkspaceChip label="합성 시연" tone="info" />
                      <WorkspaceChip
                        label={RISK_LABELS[inquiry.riskLevel]}
                        tone={getRiskTone(inquiry.riskLevel)}
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
                    <time dateTime={inquiry.updatedAt}>
                      {formatWorkspaceDateTime(inquiry.updatedAt)}
                    </time>
                  </span>

                  <strong>{inquiry.symptomLabel}</strong>
                  <small>
                    {inquiry.scenarioId} · {inquiry.customerName} ·{" "}
                    {inquiry.productCode}
                  </small>

                  <span className="v6-queue-item__bottom">
                    <WorkspaceChip
                      label={STATUS_LABELS[inquiry.status]}
                      tone={getStatusTone(inquiry.status)}
                    />
                    <b>{inquiry.id}</b>
                  </span>
                </button>
              ))
            )}
          </div>
        </aside>

        {children}
      </section>
    </>
  );
}
