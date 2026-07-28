import type { PriorityBadgeVariant } from "../../../common/components/badge/PriorityBadge";
import type { RiskLevel } from "../../../common/components/badge/RiskBadge";

export type InquiryStatus =
  | "CONSULTATION_REQUIRED"
  | "CONSULTATION_IN_PROGRESS"
  | "REOPENED";

export type InquirySort = "RECEIVED_DESC" | "RECEIVED_ASC";

export type InquiryRiskFilter = "ALL" | RiskLevel;
export type InquiryStatusFilter = "ALL" | InquiryStatus;
export type InquiryPriorityFilter = "ALL" | PriorityBadgeVariant;

export interface InquiryListItem {
  inquiryId: string;
  customerDisplayName: string;
  productModel: string;
  symptomSummary: string;
  currentState: InquiryStatus;
  riskLevel: RiskLevel;
  priorityLabel: string;
  priorityVariant: PriorityBadgeVariant;
  receivedAt: string;
}

export interface InquiryQueueFilters {
  page: number;
  priority: InquiryPriorityFilter;
  risk: InquiryRiskFilter;
  searchKeyword: string;
  sort: InquirySort;
  status: InquiryStatusFilter;
}

export interface InquiryQueuePage {
  currentPage: number;
  hasActiveFilters: boolean;
  hasChangedConditions: boolean;
  items: InquiryListItem[];
  totalItems: number;
  totalPages: number;
}
