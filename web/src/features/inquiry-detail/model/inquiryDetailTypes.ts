import type { PriorityBadgeVariant } from "../../../common/components/badge/PriorityBadge";
import type { RiskLevel } from "../../../common/components/badge/RiskBadge";

export type AllowedAction =
  | "SAVE_RESPONSE_DRAFT"
  | "SEND_RESPONSE"
  | "REQUEST_VISIT";

export type EvidenceVerificationStatus =
  | "VERIFIED"
  | "REVIEW_REQUIRED";

export interface EvidenceItem {
  documentTitle: string;
  revision: string;
  page: number;
  summary: string;
  verificationStatus: EvidenceVerificationStatus;
}

export interface InquiryEvidenceViewItem extends EvidenceItem {
  verificationLabel: string;
}

export interface StatusHistoryItem {
  status: string;
  event: string;
  actor: string;
  occurredAt: string;
}

export interface InquiryDetail {
  inquiryId: string;
  customerDisplayName: string;
  maskedPhone: string;
  productModel: string;
  subscriptionType: string;
  careType: string;
  symptomSummary: string;
  customerMessage: string;
  questionnaireAnswer: string;
  currentStateLabel: string;
  currentAssigneeLabel: string;
  riskLevel: RiskLevel;
  priorityLabel: string;
  priorityVariant: PriorityBadgeVariant;
  aiSummary: string;
  responseDraft: string;
  stateVersion: number;
  allowedActions: readonly AllowedAction[];
  evidence: readonly EvidenceItem[];
  statusHistory: readonly StatusHistoryItem[];
}

export interface InquiryDetailViewModel
  extends Omit<InquiryDetail, "evidence"> {
  evidence: readonly InquiryEvidenceViewItem[];
  isDanger: boolean;
}

export type InquiryDetailQueryResult =
  | { status: "loading" }
  | { status: "error" }
  | { status: "forbidden" }
  | { status: "notFound" }
  | { status: "success"; data: InquiryDetailViewModel };
