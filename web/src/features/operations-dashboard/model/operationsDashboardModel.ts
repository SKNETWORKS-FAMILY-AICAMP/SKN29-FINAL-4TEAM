import {
  STATUS_LABELS,
} from "../../consultation/model/consultantWorkspaceModel";
import type {
  CounselorInquiry,
  CounselorStatus,
} from "../../consultation/model/consultantWorkspaceTypes";
import type {
  OperationsDashboardSummary,
  OperationsDistributionItem,
  OperationsExceptionItem,
  OperationsFilters,
  OperationsMetric,
} from "./operationsDashboardTypes";

export const DEFAULT_OPERATIONS_FILTERS: OperationsFilters = {
  assignee: "ALL",
  managementType: "ALL",
  productModel: "ALL",
  receivedFrom: "",
  receivedTo: "",
  result: "ALL",
  risk: "ALL",
  status: "ALL",
  symptom: "ALL",
};

const VISIT_STATUSES = new Set<CounselorStatus>([
  "VISIT_REVIEW_PENDING",
  "VISIT_SCHEDULING",
  "VISIT_SCHEDULED",
  "REVISIT_REQUIRED",
]);
const CLOSED_STATUSES = new Set<CounselorStatus>(["RESOLVED", "CANCELLED"]);

function toDateKey(value: string): string {
  return value.slice(0, 10);
}

export function filterOperationsInquiries(
  inquiries: readonly CounselorInquiry[],
  filters: OperationsFilters,
): CounselorInquiry[] {
  return inquiries.filter((inquiry) => {
    if (
      filters.productModel !== "ALL" &&
      inquiry.productCode !== filters.productModel
    ) return false;
    if (
      filters.managementType !== "ALL" &&
      inquiry.managementType !== filters.managementType
    ) return false;
    if (
      filters.assignee !== "ALL" &&
      inquiry.assignedCounselor !== filters.assignee
    ) return false;
    if (
      filters.symptom !== "ALL" &&
      inquiry.symptomLabel !== filters.symptom
    ) return false;
    if (filters.risk !== "ALL" && inquiry.riskLevel !== filters.risk) {
      return false;
    }
    if (filters.status !== "ALL" && inquiry.status !== filters.status) {
      return false;
    }
    if (
      filters.receivedFrom &&
      toDateKey(inquiry.createdAt) < filters.receivedFrom
    ) return false;
    if (
      filters.receivedTo &&
      toDateKey(inquiry.createdAt) > filters.receivedTo
    ) return false;
    if (filters.result === "RESOLVED" && inquiry.status !== "RESOLVED") {
      return false;
    }
    if (
      filters.result === "IN_PROGRESS" &&
      CLOSED_STATUSES.has(inquiry.status)
    ) return false;
    return true;
  });
}

function createDistribution(
  inquiries: readonly CounselorInquiry[],
  getKey: (inquiry: CounselorInquiry) => string,
  getLabel: (key: string) => string = (key) => key,
): OperationsDistributionItem[] {
  const counts = new Map<string, number>();
  inquiries.forEach((inquiry) => {
    const key = getKey(inquiry);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  const total = inquiries.length;
  return [...counts.entries()]
    .map(([key, count]) => ({
      key,
      label: getLabel(key),
      count,
      percent: total === 0 ? 0 : Math.round((count / total) * 100),
    }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label, "ko"));
}

function getLastStep(inquiry: CounselorInquiry): string {
  if (inquiry.status === "QUESTIONNAIRE_IN_PROGRESS") return "추가 문진 수집";
  if (inquiry.aiStatus === "FAILED") return "AI·근거 확인";
  if (VISIT_STATUSES.has(inquiry.status)) return "방문 전환";
  if (inquiry.status === "CONSULTATION_IN_PROGRESS") return "상담 처리";
  if (inquiry.status === "COMPLETION_PENDING") return "고객 확인·최종 완료";
  return STATUS_LABELS[inquiry.status];
}

export function createOperationsExceptions(
  inquiries: readonly CounselorInquiry[],
): OperationsExceptionItem[] {
  return inquiries.flatMap((inquiry) => {
    const reasons: OperationsExceptionItem["reasons"][number][] = [];
    if (inquiry.nextCareDate === "확인 필요") {
      reasons.push({
        code: "CARE_SCHEDULE_MISSING",
        label: "케어 일정 미산정",
      });
    }
    if (inquiry.status === "QUESTIONNAIRE_IN_PROGRESS") {
      reasons.push({
        code: "QUESTIONNAIRE_UNANSWERED",
        label: "사전 문진 미응답",
      });
    }
    if (inquiry.waitingMinutes >= 120 && !CLOSED_STATUSES.has(inquiry.status)) {
      reasons.push({ code: "PROCESS_DELAY", label: "처리 지연" });
    }
    if (inquiry.evidence.length === 0) {
      reasons.push({
        code: "EVIDENCE_SEARCH_FAILED",
        label: "공식 근거 검색 실패",
      });
    }
    if (inquiry.aiStatus === "FAILED") {
      reasons.push({ code: "AI_PROCESS_FAILED", label: "AI 처리 실패" });
    }
    if (reasons.length === 0) return [];

    return [{
      inquiryId: inquiry.inquiryId,
      inquiryCode: inquiry.inquiryCode,
      symptomLabel: inquiry.symptomLabel,
      reasons,
      lastStep: getLastStep(inquiry),
      assignee: inquiry.assignedCounselor,
      updatedAt: inquiry.updatedAt,
      risk: inquiry.riskLevel,
    }];
  }).sort(
    (left, right) =>
      right.reasons.length - left.reasons.length ||
      new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
  );
}

function createMetrics(
  inquiries: readonly CounselorInquiry[],
): OperationsMetric[] {
  return [
    {
      key: "TOTAL",
      label: "조회 문의",
      count: inquiries.length,
      description: "현재 필터에 포함된 문의",
      tone: "default",
    },
    {
      key: "DANGER",
      label: "위험 문의",
      count: inquiries.filter((item) => item.riskLevel === "DANGER").length,
      description: "위험도 danger",
      tone: "danger",
    },
    {
      key: "CONSULTATION",
      label: "상담 전환",
      count: inquiries.filter((item) => item.requiresConsultation).length,
      description: "상담 확인이 필요한 문의",
      tone: "warning",
    },
    {
      key: "VISIT",
      label: "방문 전환",
      count: inquiries.filter((item) => VISIT_STATUSES.has(item.status)).length,
      description: "방문 검토·조율·예정·재방문",
      tone: "info",
    },
    {
      key: "RESOLVED",
      label: "처리 완료",
      count: inquiries.filter((item) => item.status === "RESOLVED").length,
      description: "최종 완료된 문의",
      tone: "success",
    },
  ];
}

export function createOperationsDashboardSummary(
  inquiries: readonly CounselorInquiry[],
  filters: OperationsFilters,
): OperationsDashboardSummary {
  const filtered = filterOperationsInquiries(inquiries, filters);
  return {
    inquiries: filtered,
    metrics: createMetrics(filtered),
    symptomDistribution: createDistribution(filtered, (item) => item.symptomLabel),
    statusDistribution: createDistribution(
      filtered,
      (item) => item.status,
      (status) => STATUS_LABELS[status as CounselorStatus] ?? "미확인",
    ),
    exceptions: createOperationsExceptions(filtered),
  };
}

export function getOperationsFilterOptions(
  inquiries: readonly CounselorInquiry[],
) {
  const unique = (values: readonly string[]) =>
    [...new Set(values)].sort((left, right) => left.localeCompare(right, "ko"));
  return {
    assignees: unique(inquiries.map((item) => item.assignedCounselor)),
    managementTypes: unique(inquiries.map((item) => item.managementType)),
    productModels: unique(inquiries.map((item) => item.productCode)),
    symptoms: unique(inquiries.map((item) => item.symptomLabel)),
  };
}
