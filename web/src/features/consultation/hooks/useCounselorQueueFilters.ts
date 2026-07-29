import { useSearchParams } from "react-router-dom";

import type {
  CounselorAssigneeFilter,
  CounselorFilters,
  CounselorPriority,
  CounselorRisk,
  CounselorSort,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";

const STATUS_VALUES: readonly ("ALL" | CounselorStatus)[] = [
  "ALL",
  "QUESTIONNAIRE_IN_PROGRESS",
  "CONSULTATION_REQUIRED",
  "CONSULTATION_IN_PROGRESS",
  "VISIT_SCHEDULED",
  "COMPLETION_PENDING",
  "UNKNOWN",
];
const RISK_VALUES: readonly ("ALL" | CounselorRisk)[] = [
  "ALL",
  "GENERAL",
  "CAUTION",
  "DANGER",
  "UNKNOWN",
];
const PRIORITY_VALUES: readonly ("ALL" | CounselorPriority)[] = [
  "ALL",
  "NORMAL",
  "HIGH",
  "URGENT",
  "UNKNOWN",
];
const ASSIGNEE_VALUES: readonly CounselorAssigneeFilter[] = [
  "ALL",
  "MINE",
  "UNASSIGNED",
];
const CONSULTATION_VALUES: readonly CounselorFilters["consultation"][] = [
  "ALL",
  "REQUIRED",
  "FINAL",
];
const SORT_VALUES: readonly CounselorSort[] = [
  "UPDATED_DESC",
  "UPDATED_ASC",
];

function readAllowed<TValue extends string>(
  searchParams: URLSearchParams,
  key: string,
  values: readonly TValue[],
  fallback: TValue,
): TValue {
  const value = searchParams.get(key);
  return value && values.includes(value as TValue)
    ? (value as TValue)
    : fallback;
}

function readPage(searchParams: URLSearchParams): number {
  const page = Number(searchParams.get("page") ?? "1");
  return Number.isInteger(page) && page > 0 ? page : 1;
}

function readDate(searchParams: URLSearchParams, key: string): string {
  const value = searchParams.get(key) ?? "";
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : "";
}

export default function useCounselorQueueFilters() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters: CounselorFilters = {
    assignee: readAllowed(searchParams, "assignee", ASSIGNEE_VALUES, "ALL"),
    consultation: readAllowed(
      searchParams,
      "consultation",
      CONSULTATION_VALUES,
      "ALL",
    ),
    page: readPage(searchParams),
    priority: readAllowed(searchParams, "priority", PRIORITY_VALUES, "ALL"),
    query: searchParams.get("q") ?? "",
    receivedFrom: readDate(searchParams, "from"),
    receivedTo: readDate(searchParams, "to"),
    risk: readAllowed(searchParams, "risk", RISK_VALUES, "ALL"),
    sort: readAllowed(searchParams, "sort", SORT_VALUES, "UPDATED_DESC"),
    status: readAllowed(searchParams, "status", STATUS_VALUES, "ALL"),
  };

  const setFilters = (next: CounselorFilters) => {
    const params = new URLSearchParams();
    const entries: readonly [string, string, string][] = [
      ["q", next.query, ""],
      ["status", next.status, "ALL"],
      ["risk", next.risk, "ALL"],
      ["priority", next.priority, "ALL"],
      ["assignee", next.assignee, "ALL"],
      ["consultation", next.consultation, "ALL"],
      ["from", next.receivedFrom, ""],
      ["to", next.receivedTo, ""],
      ["sort", next.sort, "UPDATED_DESC"],
      ["page", String(next.page), "1"],
    ];

    entries.forEach(([key, value, fallback]) => {
      if (value && value !== fallback) params.set(key, value);
    });
    setSearchParams(params, { replace: true });
  };

  const updateFilters = (next: CounselorFilters) => {
    const changedConditions = Object.entries(next).some(
      ([key, value]) => key !== "page" && value !== filters[key as keyof CounselorFilters],
    );
    setFilters({ ...next, page: changedConditions ? 1 : next.page });
  };

  return {
    filters,
    hasChangedConditions:
      filters.query.length > 0 ||
      filters.status !== "ALL" ||
      filters.risk !== "ALL" ||
      filters.priority !== "ALL" ||
      filters.assignee !== "ALL" ||
      filters.consultation !== "ALL" ||
      filters.receivedFrom.length > 0 ||
      filters.receivedTo.length > 0 ||
      filters.sort !== "UPDATED_DESC",
    resetFilters: () => setSearchParams(new URLSearchParams(), { replace: true }),
    setFilters: updateFilters,
  };
}
