import { useLocation, useNavigate } from "react-router-dom";

import { createInquiryDetailPath } from "../../app/router/routePaths";
import PriorityBadge from "../../common/components/badge/PriorityBadge";
import RiskBadge from "../../common/components/badge/RiskBadge";
import StatusBadge from "../../common/components/badge/StatusBadge";
import Pagination from "../../common/components/data-display/Pagination";
import EmptyState from "../../common/components/feedback/EmptyState";
import useInquiryQueueFilters from "../../features/inquiry-queue/hooks/useInquiryQueueFilters";
import useMockInquiryQueue from "../../features/inquiry-queue/hooks/useMockInquiryQueue";
import {
  INQUIRY_QUEUE_PAGE_SIZE,
  STATUS_LABELS,
  STATUS_VARIANTS,
} from "../../features/inquiry-queue/model/inquiryQueueConstants";
import { formatInquiryReceivedAt } from "../../features/inquiry-queue/model/inquiryQueueModel";
import "./ConsultantDashboardPage.css";

export default function ConsultantDashboardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    filters,
    resetFilters,
    setPage,
    setPriority,
    setRisk,
    setSearchKeyword,
    setSort,
    setStatus,
  } = useInquiryQueueFilters();
  const queue = useMockInquiryQueue(filters);

  const handleInquiryClick = (inquiryId: string) => {
    navigate(createInquiryDetailPath(inquiryId), {
      state: {
        returnTo: `${location.pathname}${location.search}`,
      },
    });
  };

  return (
    <main className="consultant-dashboard">
      <header className="consultant-dashboard__header">
        <div>
          <p className="consultant-dashboard__eyebrow">CONS-01</p>
          <h1>상담사 문의 목록</h1>
          <p>접수된 문의를 확인하고 처리할 문의를 선택하세요.</p>
        </div>

        <div className="consultant-dashboard__count">
          검색 결과 <strong>{queue.totalItems}</strong>건
        </div>
      </header>

      <section
        className="consultant-dashboard__filters"
        aria-label="문의 검색 및 필터"
      >
        <label>
          <span>문의 검색</span>

          <input
            type="search"
            value={filters.searchKeyword}
            onChange={(event) => setSearchKeyword(event.target.value)}
            placeholder="문의 번호, 고객명, 제품, 증상 검색"
          />
        </label>

        <label>
          <span>위험도</span>

          <select
            value={filters.risk}
            onChange={(event) => setRisk(event.target.value)}
          >
            <option value="ALL">전체</option>
            <option value="general">일반</option>
            <option value="caution">주의</option>
            <option value="danger">위험</option>
          </select>
        </label>

        <label>
          <span>상태</span>

          <select
            value={filters.status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="ALL">전체</option>
            <option value="CONSULTATION_REQUIRED">상담 필요</option>
            <option value="CONSULTATION_IN_PROGRESS">상담 진행 중</option>
            <option value="REOPENED">문의 재개</option>
          </select>
        </label>

        <label>
          <span>우선순위</span>

          <select
            value={filters.priority}
            onChange={(event) => setPriority(event.target.value)}
          >
            <option value="ALL">전체</option>
            <option value="default">보통</option>
            <option value="high">높음</option>
            <option value="urgent">긴급</option>
          </select>
        </label>

        <label>
          <span>정렬</span>

          <select
            value={filters.sort}
            onChange={(event) => setSort(event.target.value)}
          >
            <option value="RECEIVED_DESC">접수 시각 최신순</option>
            <option value="RECEIVED_ASC">접수 시각 오래된순</option>
          </select>
        </label>

        <div className="consultant-dashboard__filter-footer">
          <p className="consultant-dashboard__mock-notice">
            {`현재 목록과 우선순위 필터는 Mock 데이터 기준이며 페이지당 ${INQUIRY_QUEUE_PAGE_SIZE}건을 표시합니다.`}
          </p>

          {queue.hasChangedConditions && (
            <button
              type="button"
              className="consultant-dashboard__reset-button"
              onClick={resetFilters}
            >
              검색 조건 초기화
            </button>
          )}
        </div>
      </section>

      <section className="consultant-dashboard__content">
        {queue.totalItems === 0 ? (
          <EmptyState
            title={
              queue.hasActiveFilters
                ? "검색 결과가 없습니다."
                : "접수된 문의가 없습니다."
            }
            description={
              queue.hasActiveFilters
                ? "검색어나 필터 조건을 변경한 뒤 다시 확인해 주세요."
                : "새 문의가 접수되면 이 목록에 표시됩니다."
            }
          />
        ) : (
          <div className="consultant-dashboard__table-wrap">
            <table className="consultant-dashboard__table">
              <thead>
                <tr>
                  <th>문의 번호</th>
                  <th>고객</th>
                  <th>제품 모델</th>
                  <th>대표 증상</th>
                  <th>상태</th>
                  <th>위험도</th>
                  <th>우선순위</th>
                  <th>접수 시각</th>
                  <th aria-label="상세 보기" />
                </tr>
              </thead>

              <tbody>
                {queue.items.map((inquiry) => (
                  <tr key={inquiry.inquiryId}>
                    <td>
                      <strong>{inquiry.inquiryId}</strong>
                    </td>

                    <td>{inquiry.customerDisplayName}</td>
                    <td>{inquiry.productModel}</td>
                    <td>{inquiry.symptomSummary}</td>

                    <td>
                      <StatusBadge
                        label={STATUS_LABELS[inquiry.currentState]}
                        variant={STATUS_VARIANTS[inquiry.currentState]}
                      />
                    </td>

                    <td>
                      <RiskBadge level={inquiry.riskLevel} />
                    </td>

                    <td>
                      <PriorityBadge
                        label={inquiry.priorityLabel}
                        variant={inquiry.priorityVariant}
                      />
                    </td>

                    <td>{formatInquiryReceivedAt(inquiry.receivedAt)}</td>

                    <td>
                      <button
                        type="button"
                        className="detail-button"
                        onClick={() => handleInquiryClick(inquiry.inquiryId)}
                      >
                        상세 보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <Pagination
              page={queue.currentPage}
              totalItems={queue.totalItems}
              totalPages={queue.totalPages}
              onPageChange={setPage}
            />
          </div>
        )}
      </section>
    </main>
  );
}
