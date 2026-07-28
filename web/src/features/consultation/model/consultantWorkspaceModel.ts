import type {
  CounselorFilters,
  CounselorInquiry,
  CounselorRisk,
  CounselorStatus,
} from "./consultantWorkspaceTypes";

export const STATUS_LABELS: Record<CounselorStatus, string> = {
  QUESTIONNAIRE_IN_PROGRESS: "문진 진행 중",
  CONSULTATION_REQUIRED: "상담 대기",
  CONSULTATION_IN_PROGRESS: "상담 진행 중",
  VISIT_SCHEDULED: "방문 예정",
  COMPLETION_PENDING: "최종 완료 대기",
};

export const RISK_LABELS: Record<CounselorRisk, string> = {
  GENERAL: "일반",
  CAUTION: "주의",
  DANGER: "위험",
};

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

  if (status === "VISIT_SCHEDULED") return "purple";
  return "info";
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
      inquiry.symptomLabel,
      inquiry.customerName,
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
  });
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
    visit: inquiries.filter((item) => item.status === "VISIT_SCHEDULED")
      .length,
    finalizable: inquiries.filter(
      (item) =>
        item.status === "COMPLETION_PENDING" && item.feedbackResolved,
    ).length,
  };
}
