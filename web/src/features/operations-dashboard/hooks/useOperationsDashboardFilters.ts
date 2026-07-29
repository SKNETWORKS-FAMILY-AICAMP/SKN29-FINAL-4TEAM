import { useSearchParams } from "react-router-dom";

import {
  DEFAULT_OPERATIONS_FILTERS,
} from "../model/operationsDashboardModel";
import type { OperationsFilters } from "../model/operationsDashboardTypes";
import type {
  CounselorRisk,
  CounselorStatus,
} from "../../consultation/model/consultantWorkspaceTypes";

const RISK_VALUES: readonly ("ALL" | CounselorRisk)[] = [
  "ALL",
  "GENERAL",
  "CAUTION",
  "DANGER",
  "UNKNOWN",
];
const STATUS_VALUES: readonly ("ALL" | CounselorStatus)[] = [
  "ALL",
  "DRAFT",
  "QUESTIONNAIRE_IN_PROGRESS",
  "AI_GUIDANCE",
  "CONSULTATION_REQUIRED",
  "CONSULTATION_IN_PROGRESS",
  "VISIT_REVIEW_PENDING",
  "VISIT_SCHEDULING",
  "VISIT_SCHEDULED",
  "COMPLETION_PENDING",
  "REVISIT_REQUIRED",
  "REOPENED",
  "RESOLVED",
  "CANCELLED",
  "UNKNOWN",
];
const RESULT_VALUES: readonly OperationsFilters["result"][] = [
  "ALL",
  "RESOLVED",
  "IN_PROGRESS",
];

function readAllowed<TValue extends string>(
  params: URLSearchParams,
  key: string,
  values: readonly TValue[],
  fallback: TValue,
): TValue {
  const value = params.get(key);
  return value && values.includes(value as TValue) ? (value as TValue) : fallback;
}

function readDate(params: URLSearchParams, key: string): string {
  const value = params.get(key) ?? "";
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";
}

export default function useOperationsDashboardFilters() {
  const [params, setParams] = useSearchParams();
  const filters: OperationsFilters = {
    assignee: params.get("assignee") || "ALL",
    managementType: params.get("management") || "ALL",
    productModel: params.get("model") || "ALL",
    receivedFrom: readDate(params, "from"),
    receivedTo: readDate(params, "to"),
    result: readAllowed(params, "result", RESULT_VALUES, "ALL"),
    risk: readAllowed(params, "risk", RISK_VALUES, "ALL"),
    status: readAllowed(params, "status", STATUS_VALUES, "ALL"),
    symptom: params.get("symptom") || "ALL",
  };

  const setFilters = (next: OperationsFilters) => {
    const nextParams = new URLSearchParams();
    const mockState = params.get("mockState");
    if (mockState) nextParams.set("mockState", mockState);
    const entries: readonly [string, string, string][] = [
      ["from", next.receivedFrom, ""],
      ["to", next.receivedTo, ""],
      ["model", next.productModel, "ALL"],
      ["management", next.managementType, "ALL"],
      ["assignee", next.assignee, "ALL"],
      ["symptom", next.symptom, "ALL"],
      ["risk", next.risk, "ALL"],
      ["status", next.status, "ALL"],
      ["result", next.result, "ALL"],
    ];
    entries.forEach(([key, value, fallback]) => {
      if (value && value !== fallback) nextParams.set(key, value);
    });
    setParams(nextParams, { replace: true });
  };

  return {
    filters,
    hasChangedFilters: Object.entries(filters).some(
      ([key, value]) => value !== DEFAULT_OPERATIONS_FILTERS[key as keyof OperationsFilters],
    ),
    resetFilters: () => setFilters(DEFAULT_OPERATIONS_FILTERS),
    setFilters,
  };
}
