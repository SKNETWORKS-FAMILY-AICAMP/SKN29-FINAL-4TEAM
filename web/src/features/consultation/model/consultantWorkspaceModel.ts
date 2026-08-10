import type {
  CounselorFilters,
  CounselorInquiry,
  CounselorPriority,
  CounselorRoutingTarget,
  CounselorQueuePage,
  CounselorRisk,
  CounselorStatus,
  CounselorWorkBucket,
} from "./consultantWorkspaceTypes";
import type { PriorityBadgeVariant } from "../../../common/components/badge/PriorityBadge";
import type { StatusBadgeVariant } from "../../../common/components/badge/StatusBadge";
import { formatContractDateTimeLong } from "../../../common/date-time/contractDateTime";

export const COUNSELOR_QUEUE_PAGE_SIZE = 10;

export const STATUS_LABELS: Record<CounselorStatus, string> = {
  DRAFT: "작성 중",
  QUESTIONNAIRE_IN_PROGRESS: "문진 진행 중",
  AI_GUIDANCE: "AI 안내 완료",
  CONSULTATION_REQUIRED: "상담 대기",
  CONSULTATION_IN_PROGRESS: "상담 진행 중",
  VISIT_REVIEW_PENDING: "방문 필요 검토 중",
  VISIT_SCHEDULING: "방문 일정 조율 중",
  VISIT_SCHEDULED: "방문 예정",
  COMPLETION_PENDING: "최종 완료 대기",
  REVISIT_REQUIRED: "재방문 필요",
  REOPENED: "문의 재개",
  RESOLVED: "처리 완료",
  CANCELLED: "취소",
  UNKNOWN: "미확인",
};

export const RISK_LABELS: Record<CounselorRisk, string> = {
  GENERAL: "일반",
  CAUTION: "주의",
  DANGER: "긴급",
  UNKNOWN: "미확인",
};

export const WORK_BUCKET_LABELS: Record<CounselorWorkBucket, string> = {
  NEW: "새로 들어온 문의",
  IN_PROGRESS: "처리 중인 문의",
  COMPLETED: "처리 완료된 문의",
};

export function getCounselorWorkBucket(
  status: CounselorStatus,
): CounselorWorkBucket {
  if (status === "RESOLVED" || status === "CANCELLED") {
    return "COMPLETED";
  }

  if (status === "CONSULTATION_REQUIRED" || status === "REOPENED") {
    return "NEW";
  }

  return "IN_PROGRESS";
}

export interface CounselorRoutingDecision {
  target: CounselorRoutingTarget;
  reason: string;
}

export function getCounselorRoutingDecision(
  risk: CounselorRisk,
): CounselorRoutingDecision {
  if (risk === "GENERAL") {
    return {
      target: "FIELD_TECHNICIAN",
      reason: "일반 문의는 AI가 방문기사에게 자동 인계합니다.",
    };
  }

  return {
    target: "CONSULTANT",
    reason:
      risk === "DANGER"
        ? "긴급 문의는 상담사가 안전 안내를 먼저 확인합니다."
        : risk === "CAUTION"
          ? "주의 문의는 상담사가 안내 내용을 먼저 확인합니다."
          : "위험도를 확인할 수 없어 상담사가 먼저 확인합니다.",
  };
}

export const PRIORITY_LABELS: Record<CounselorPriority, string> = {
  LOW: "낮음",
  NORMAL: "보통",
  HIGH: "높음",
  URGENT: "긴급",
  UNKNOWN: "미확인",
};

const COUNSELOR_STATUSES = new Set<CounselorStatus>(
  Object.keys(STATUS_LABELS) as CounselorStatus[],
);
const COUNSELOR_RISKS = new Set<CounselorRisk>(
  Object.keys(RISK_LABELS) as CounselorRisk[],
);

export function normalizeCounselorStatus(value: unknown): CounselorStatus {
  return typeof value === "string" &&
    COUNSELOR_STATUSES.has(value as CounselorStatus)
    ? (value as CounselorStatus)
    : "UNKNOWN";
}

export function normalizeCounselorRisk(value: unknown): CounselorRisk {
  const normalized = typeof value === "string" ? value.toUpperCase() : "";
  return COUNSELOR_RISKS.has(normalized as CounselorRisk)
    ? (normalized as CounselorRisk)
    : "UNKNOWN";
}

export function getPriorityVariant(
  priority: CounselorPriority,
): PriorityBadgeVariant {
  if (priority === "URGENT") return "urgent";
  if (priority === "HIGH") return "high";
  return "default";
}

export function getStatusBadgeVariant(
  status: CounselorStatus,
): StatusBadgeVariant {
  if (status === "RESOLVED") return "success";
  if (status === "CONSULTATION_IN_PROGRESS") return "progress";
  if (
    status === "VISIT_REVIEW_PENDING" ||
    status === "VISIT_SCHEDULING" ||
    status === "VISIT_SCHEDULED" ||
    status === "REVISIT_REQUIRED" ||
    status === "REOPENED"
  ) {
    return "reopened";
  }
  return "default";
}

export function getRiskTone(risk: CounselorRisk): string {
  if (risk === "DANGER") return "danger";
  if (risk === "CAUTION") return "warning";
  return risk === "GENERAL" ? "success" : "default";
}

export function getStatusTone(status: CounselorStatus): string {
  if (status === "RESOLVED") return "success";
  if (status === "CANCELLED" || status === "UNKNOWN") return "default";
  return "info";
}

export function formatWaitingTime(minutes: number): string {
  if (minutes < 60) return `${minutes}분`;

  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder === 0 ? `${hours}시간` : `${hours}시간 ${remainder}분`;
}

export function formatWorkspaceDateTime(value: string): string {
  return formatContractDateTimeLong(value) ?? value;
}

export function filterCounselorInquiries(
  inquiries: readonly CounselorInquiry[],
  filters: CounselorFilters,
): CounselorInquiry[] {
  const query = filters.query.trim().toLocaleLowerCase("ko-KR");

  return inquiries.filter((inquiry) => {
    const searchable = [
      inquiry.inquiryId,
      inquiry.inquiryCode,
      inquiry.scenarioId,
      ...inquiry.symptomLabels,
      inquiry.customerName,
      inquiry.customerDisplayName,
      inquiry.productCode,
      inquiry.customerMessage,
    ]
      .join(" ")
      .toLocaleLowerCase("ko-KR");

    if (query && !searchable.includes(query)) return false;
    if (filters.status !== "ALL" && inquiry.status !== filters.status) {
      return false;
    }
    if (filters.risk !== "ALL" && inquiry.riskLevel !== filters.risk) {
      return false;
    }
    if (
      filters.priority !== "ALL" &&
      inquiry.priority !== filters.priority
    ) {
      return false;
    }
    if (
      filters.assignee === "MINE" &&
      inquiry.assignedCounselor !== "한유진"
    ) {
      return false;
    }
    if (
      filters.assignee === "UNASSIGNED" &&
      inquiry.assignedCounselor !== "미배정"
    ) {
      return false;
    }
    if (
      filters.receivedFrom &&
      inquiry.createdAt.slice(0, 10) < filters.receivedFrom
    ) {
      return false;
    }
    if (
      filters.receivedTo &&
      inquiry.createdAt.slice(0, 10) > filters.receivedTo
    ) {
      return false;
    }
    if (
      filters.consultation === "REQUIRED" &&
      !inquiry.requiresConsultation
    ) {
      return false;
    }
    if (
      filters.consultation === "FINAL" &&
      !(inquiry.status === "COMPLETION_PENDING" &&
        inquiry.feedbackResolved)
    ) {
      return false;
    }

    return true;
  }).sort((left, right) => {
    if (filters.sort === "WAITING_DESC") {
      return right.waitingMinutes - left.waitingMinutes;
    }
    if (filters.sort === "RISK_DESC") {
      const riskScore = { DANGER: 3, CAUTION: 2, GENERAL: 1, UNKNOWN: 0 };
      const riskDifference =
        riskScore[right.riskLevel] - riskScore[left.riskLevel];
      return riskDifference || right.waitingMinutes - left.waitingMinutes;
    }
    const difference =
      new Date(right.updatedAt).getTime() -
      new Date(left.updatedAt).getTime();
    return filters.sort === "UPDATED_DESC" ? difference : -difference;
  });
}

export function getCounselorQueuePage(
  inquiries: readonly CounselorInquiry[],
  filters: CounselorFilters,
): CounselorQueuePage {
  const filtered = filterCounselorInquiries(inquiries, filters);
  const totalPages = Math.max(
    1,
    Math.ceil(filtered.length / COUNSELOR_QUEUE_PAGE_SIZE),
  );
  const currentPage = Math.min(filters.page, totalPages);
  const startIndex = (currentPage - 1) * COUNSELOR_QUEUE_PAGE_SIZE;

  return {
    currentPage,
    items: filtered.slice(
      startIndex,
      startIndex + COUNSELOR_QUEUE_PAGE_SIZE,
    ),
    totalItems: filtered.length,
    totalPages,
  };
}

export function getCounselorMetrics(
  inquiries: readonly CounselorInquiry[],
) {
  return {
    consultation: inquiries.filter(
      (item) => item.status === "CONSULTATION_REQUIRED",
    ).length,
    danger: inquiries.filter((item) => item.riskLevel === "DANGER")
      .length,
    visit: inquiries.filter((item) =>
      [
        "VISIT_REVIEW_PENDING",
        "VISIT_SCHEDULING",
        "VISIT_SCHEDULED",
        "REVISIT_REQUIRED",
      ].includes(item.status),
    ).length,
    finalizable: inquiries.filter(
      (item) =>
        item.status === "COMPLETION_PENDING" && item.feedbackResolved,
    ).length,
  };
}
