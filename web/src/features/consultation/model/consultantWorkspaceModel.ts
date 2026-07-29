import type {
  CounselorFilters,
  CounselorInquiry,
  CounselorPriority,
  CounselorQueuePage,
  CounselorRisk,
  CounselorStatus,
} from "./consultantWorkspaceTypes";
import type { PriorityBadgeVariant } from "../../../common/components/badge/PriorityBadge";
import type { StatusBadgeVariant } from "../../../common/components/badge/StatusBadge";

export const COUNSELOR_QUEUE_PAGE_SIZE = 3;

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
};

export const RISK_LABELS: Record<CounselorRisk, string> = {
  GENERAL: "일반",
  CAUTION: "주의",
  DANGER: "위험",
};

export const PRIORITY_LABELS: Record<CounselorPriority, string> = {
  NORMAL: "보통",
  HIGH: "높음",
  URGENT: "긴급",
};

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
  if (status === "COMPLETION_PENDING" || status === "RESOLVED") {
    return "success";
  }
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
  return "success";
}

export function getStatusTone(status: CounselorStatus): string {
  if (
    status === "COMPLETION_PENDING" ||
    status === "CONSULTATION_REQUIRED"
  ) {
    return "warning";
  }

  if (
    status === "VISIT_REVIEW_PENDING" ||
    status === "VISIT_SCHEDULING" ||
    status === "VISIT_SCHEDULED" ||
    status === "REVISIT_REQUIRED" ||
    status === "REOPENED"
  ) {
    return "purple";
  }
  return "info";
}

export function formatWaitingTime(minutes: number): string {
  if (minutes < 60) return `${minutes}분`;

  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder === 0 ? `${hours}시간` : `${hours}시간 ${remainder}분`;
}

export function formatWorkspaceDateTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  }).format(date);
}

export function filterCounselorInquiries(
  inquiries: readonly CounselorInquiry[],
  filters: CounselorFilters,
): CounselorInquiry[] {
  const query = filters.query.trim().toLocaleLowerCase("ko-KR");

  return inquiries.filter((inquiry) => {
    const searchable = [
      inquiry.id,
      inquiry.scenarioId,
      ...inquiry.symptomLabels,
      inquiry.customerName,
      inquiry.customerDisplayName,
      inquiry.productCode,
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
