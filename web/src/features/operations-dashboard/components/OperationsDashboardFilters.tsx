import {
  STATUS_LABELS,
} from "../../consultation/model/consultantWorkspaceModel";
import type {
  CounselorRisk,
  CounselorStatus,
} from "../../consultation/model/consultantWorkspaceTypes";
import type { OperationsFilters } from "../model/operationsDashboardTypes";

interface OperationsDashboardFiltersProps {
  filters: OperationsFilters;
  hasChangedFilters: boolean;
  options: {
    assignees: readonly string[];
    managementTypes: readonly string[];
    productModels: readonly string[];
    symptoms: readonly string[];
  };
  resultCount: number;
  onChange: (filters: OperationsFilters) => void;
  onReset: () => void;
}

const FILTERABLE_STATUSES = Object.entries(STATUS_LABELS) as readonly [
  CounselorStatus,
  string,
][];

export default function OperationsDashboardFilters({
  filters,
  hasChangedFilters,
  options,
  resultCount,
  onChange,
  onReset,
}: OperationsDashboardFiltersProps) {
  const update = <Key extends keyof OperationsFilters>(
    key: Key,
    value: OperationsFilters[Key],
  ) => onChange({ ...filters, [key]: value });

  return (
    <section className="operations-panel operations-filters" aria-label="운영 현황 조회 필터">
      <div className="operations-section-head operations-filters__head">
        <div>
          <small>FILTER</small>
          <h2>운영 현황 조회 조건</h2>
        </div>
        <strong>{resultCount}건</strong>
      </div>

      <div className="operations-filters__grid">
        <label>
          조회 시작일
          <input
            type="date"
            value={filters.receivedFrom}
            onChange={(event) => update("receivedFrom", event.target.value)}
          />
        </label>
        <label>
          조회 종료일
          <input
            type="date"
            value={filters.receivedTo}
            onChange={(event) => update("receivedTo", event.target.value)}
          />
        </label>
        <label>
          제품 모델
          <select
            value={filters.productModel}
            onChange={(event) => update("productModel", event.target.value)}
          >
            <option value="ALL">전체 모델</option>
            {options.productModels.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          관리 유형
          <select
            value={filters.managementType}
            onChange={(event) => update("managementType", event.target.value)}
          >
            <option value="ALL">전체 관리 유형</option>
            {options.managementTypes.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          처리 담당자
          <select
            value={filters.assignee}
            onChange={(event) => update("assignee", event.target.value)}
          >
            <option value="ALL">전체 담당자</option>
            {options.assignees.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          증상 유형
          <select
            value={filters.symptom}
            onChange={(event) => update("symptom", event.target.value)}
          >
            <option value="ALL">전체 증상</option>
            {options.symptoms.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          위험도
          <select
            value={filters.risk}
            onChange={(event) =>
              update("risk", event.target.value as "ALL" | CounselorRisk)
            }
          >
            <option value="ALL">전체 위험도</option>
            <option value="DANGER">위험</option>
            <option value="CAUTION">주의</option>
            <option value="GENERAL">일반</option>
            <option value="UNKNOWN">미확인</option>
          </select>
        </label>
        <label>
          문의 상태
          <select
            value={filters.status}
            onChange={(event) =>
              update("status", event.target.value as "ALL" | CounselorStatus)
            }
          >
            <option value="ALL">전체 상태</option>
            {FILTERABLE_STATUSES.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label>
          처리 결과
          <select
            value={filters.result}
            onChange={(event) =>
              update("result", event.target.value as OperationsFilters["result"])
            }
          >
            <option value="ALL">전체 처리 결과</option>
            <option value="RESOLVED">처리 완료</option>
            <option value="IN_PROGRESS">처리 중</option>
          </select>
        </label>
      </div>

      <div className="operations-filters__footer">
        <p>공식 합성 문의를 기준으로 집계하며 실제 운영 데이터는 사용하지 않습니다.</p>
        <button type="button" disabled={!hasChangedFilters} onClick={onReset}>
          조건 초기화
        </button>
      </div>
    </section>
  );
}
