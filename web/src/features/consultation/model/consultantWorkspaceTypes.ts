import type {
  InquiryCode,
  InquiryId,
} from "../../../entities/inquiry/inquiryIdentifiers";

export type CounselorRisk = "GENERAL" | "CAUTION" | "DANGER" | "UNKNOWN";

export type CounselorStatus =
  | "DRAFT"
  | "QUESTIONNAIRE_IN_PROGRESS"
  | "AI_GUIDANCE"
  | "CONSULTATION_REQUIRED"
  | "CONSULTATION_IN_PROGRESS"
  | "VISIT_REVIEW_PENDING"
  | "VISIT_SCHEDULING"
  | "VISIT_SCHEDULED"
  | "COMPLETION_PENDING"
  | "REVISIT_REQUIRED"
  | "REOPENED"
  | "RESOLVED"
  | "CANCELLED"
  | "UNKNOWN";

export type CounselorPriority = "NORMAL" | "HIGH" | "URGENT" | "UNKNOWN";
export type CounselorSort = "UPDATED_DESC" | "UPDATED_ASC";
export type CounselorAssigneeFilter = "ALL" | "MINE" | "UNASSIGNED";

export type DetailTab = "summary" | "answers" | "evidence" | "timeline";

export type CounselorActionCode =
  | "START_CONSULTATION"
  | "UPDATE_CONSULTATION_SUMMARY"
  | "CONFIRM_CONSULTATION_SUMMARY"
  | "CONSULTATION_COMPLETED"
  | "VISIT_REVIEW_REQUIRED"
  | "VISIT_NEEDED"
  | "VISIT_NOT_NEEDED"
  | "UPDATE_VISIT_SCHEDULE"
  | "CONFIRM_VISIT"
  | "RESUME_CONSULTATION"
  | "FINALIZE_INQUIRY";

export interface CounselorAllowedAction {
  code: CounselorActionCode;
  label: string;
  operationId: string;
  style: "PRIMARY" | "SECONDARY" | "DESTRUCTIVE";
  requiresConfirmation: boolean;
  confirmationMessage: string | null;
}

export interface CounselorEvidence {
  documentTitle: string;
  summary: string;
  documentVersion: string;
  page: number;
  verificationLabel: string;
  dataClassification: "official" | "team_designed" | "synthetic";
  sourceLandingUrl: string;
}

export interface CounselorTimelineItem {
  title: string;
  description: string;
  actor: string;
  occurredAt: string;
}

export interface CounselorInquiry {
  inquiryId: InquiryId;
  inquiryCode: InquiryCode;
  scenarioId: string;
  customerId: string;
  customerName: string;
  customerDisplayName: string;
  subscriptionId: string;
  productCode: string;
  manualModel: string;
  symptomLabel: string;
  symptomLabels: readonly string[];
  customerMessage: string;
  conditions: string;
  displayCode: string;
  performedAction: string;
  actionResult: string;
  status: CounselorStatus;
  riskLevel: CounselorRisk;
  priority: CounselorPriority;
  requiresConsultation: boolean;
  feedbackResolved: boolean;
  feedbackComment?: string;
  createdAt: string;
  updatedAt: string;
  waitingMinutes: number;
  assignedCounselor: string;
  managementType: string;
  serviceStartDate: string;
  lastCareDate: string;
  lastFilterDate: string;
  nextCareDate: string;
  nextCareBasis: string;
  usageStatus:
    | "NORMAL"
    | "PARTIAL_STOP"
    | "TOTAL_STOP"
    | "PENDING_CONSULTATION";
  usageMessage: string;
  restrictedWaterTypes: readonly string[];
  restrictedFunctions: readonly string[];
  guidanceBasis: string;
  nextAction: string;
  aiStatus: "COMPLETED" | "FAILED";
  aiOutcome: string;
  aiSummaryOriginal: string;
  aiSummaryRevision?: string;
  confirmedSummary?: string;
  stateVersion: number;
  allowedActions: readonly CounselorAllowedAction[];
  evidence: readonly CounselorEvidence[];
  timeline: readonly CounselorTimelineItem[];
}

export interface CounselorFilters {
  assignee: CounselorAssigneeFilter;
  consultation: "ALL" | "REQUIRED" | "FINAL";
  page: number;
  priority: "ALL" | CounselorPriority;
  query: string;
  receivedFrom: string;
  receivedTo: string;
  risk: "ALL" | CounselorRisk;
  sort: CounselorSort;
  status: "ALL" | CounselorStatus;
}

export interface CounselorQueuePage {
  currentPage: number;
  items: CounselorInquiry[];
  totalItems: number;
  totalPages: number;
}
