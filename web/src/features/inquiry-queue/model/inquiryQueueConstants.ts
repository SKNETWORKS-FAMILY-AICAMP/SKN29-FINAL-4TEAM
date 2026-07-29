import type {
  InquiryPriorityFilter,
  InquiryRiskFilter,
  InquirySort,
  InquiryStatus,
  InquiryStatusFilter,
} from "./inquiryQueueTypes";

export const INQUIRY_QUEUE_PAGE_SIZE = 2;

export const RISK_FILTER_VALUES: readonly InquiryRiskFilter[] = [
  "ALL",
  "general",
  "caution",
  "danger",
];

export const STATUS_FILTER_VALUES: readonly InquiryStatusFilter[] = [
  "ALL",
  "CONSULTATION_REQUIRED",
  "CONSULTATION_IN_PROGRESS",
  "REOPENED",
];

export const PRIORITY_FILTER_VALUES: readonly InquiryPriorityFilter[] = [
  "ALL",
  "default",
  "high",
  "urgent",
];

export const SORT_VALUES: readonly InquirySort[] = [
  "RECEIVED_DESC",
  "RECEIVED_ASC",
];

export const STATUS_LABELS: Record<InquiryStatus, string> = {
  CONSULTATION_REQUIRED: "상담 필요",
  CONSULTATION_IN_PROGRESS: "상담 진행 중",
  REOPENED: "문의 재개",
};

export const STATUS_VARIANTS: Record<
  InquiryStatus,
  "default" | "progress" | "reopened"
> = {
  CONSULTATION_REQUIRED: "default",
  CONSULTATION_IN_PROGRESS: "progress",
  REOPENED: "reopened",
};
