import FormSelect from "../../../common/components/form/FormSelect";
import {
  STATUS_LABELS,
} from "../../consultation/model/consultantWorkspaceModel";
import type {
  CounselorRisk,
  CounselorStatus,
} from "../../consultation/model/consultantWorkspaceTypes";
import { formatProductModelAndName } from "../../consultation/model/productDisplayName";
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
          <FormSelect
            value={filters.productModel}
            onChange={(value) => update("productModel", value)}
            options={[
              { value: "ALL", label: "전체 모델" },
              ...options.productModels.map((value) => ({ value, label: formatProductModelAndName(value) })),
            ]}
          />
        </label>
        <label>
          관리 유형
          <FormSelect
            value={filters.managementType}
            onChange={(value) => update("managementType", value)}
            options={[
              { value: "ALL", label: "전체 관리 유형" },
              ...options.managementTypes.map((value) => ({ value, label: value })),
            ]}
          />
        </label>
        <label>
          처리 담당자
          <FormSelect
            value={filters.assignee}
            onChange={(value) => update("assignee", value)}
            options={[
              { value: "ALL", label: "전체 담당자" },
              ...options.assignees.map((value) => ({ value, label: value })),
            ]}
          />
        </label>
        <label>
          증상 유형
          <FormSelect
            value={filters.symptom}
            onChange={(value) => update("symptom", value)}
            options={[
              { value: "ALL", label: "전체 증상" },
              ...options.symptoms.map((value) => ({ value, label: value })),
            ]}
          />
        </label>
        <label>
          위험도
          <FormSelect
            value={filters.risk}
            onChange={(value) =>
              update("risk", value as "ALL" | CounselorRisk)
            }
            options={[
              { value: "ALL", label: "전체 위험도" },
              { value: "DANGER", label: "긴급" },
              { value: "CAUTION", label: "주의" },
              { value: "GENERAL", label: "일반" },
              { value: "UNKNOWN", label: "미확인" },
            ]}
          />
        </label>
        <label>
          문의 상태
          <FormSelect
            value={filters.status}
            onChange={(value) =>
              update("status", value as "ALL" | CounselorStatus)
            }
            options={[
              { value: "ALL", label: "전체 상태" },
              ...FILTERABLE_STATUSES.map(([value, label]) => ({ value, label })),
            ]}
          />
        </label>
        <label>
          처리 결과
          <FormSelect
            value={filters.result}
            onChange={(value) =>
              update("result", value as OperationsFilters["result"])
            }
            options={[
              { value: "ALL", label: "전체 처리 결과" },
              { value: "RESOLVED", label: "처리 완료" },
              { value: "IN_PROGRESS", label: "처리 중" },
            ]}
          />
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
