export type CounselorRisk = "GENERAL" | "CAUTION" | "DANGER";

export type CounselorStatus =
  | "QUESTIONNAIRE_IN_PROGRESS"
  | "CONSULTATION_REQUIRED"
  | "CONSULTATION_IN_PROGRESS"
  | "VISIT_SCHEDULED"
  | "COMPLETION_PENDING";

export type CounselorPriority = "NORMAL" | "HIGH" | "URGENT";
export type CounselorSort = "UPDATED_DESC" | "UPDATED_ASC";
export type CounselorAssigneeFilter = "ALL" | "MINE" | "UNASSIGNED";

export type DetailTab = "summary" | "answers" | "evidence" | "timeline";

export type CounselorActionCode =
  | "START_CONSULTATION"
  | "UPDATE_CONSULTATION_SUMMARY"
  | "CONFIRM_CONSULTATION_SUMMARY"
  | "CONSULTATION_COMPLETED"
  | "VISIT_REVIEW_REQUIRED"
  | "UPDATE_VISIT_SCHEDULE"
  | "CONFIRM_VISIT"
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
  evidenceId: string;
  documentVersion: string;
  page: number;
  sectionTitle: string;
  riskLevel: string;
  safeActions: readonly string[];
  prohibitedActions: readonly string[];
  sourceLandingUrl: string;
  sourceDirectDownloadUrl: string;
}

export interface CounselorTimelineItem {
  title: string;
  description: string;
  actor: string;
  occurredAt: string;
}

export interface CounselorInquiry {
  id: string;
  scenarioId: string;
  customerId: string;
  customerName: string;
  subscriptionId: string;
  productCode: string;
  manualModel: string;
  symptomLabel: string;
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
  assignedCounselor: string;
  managementType: string;
  serviceStartDate: string;
  lastCareDate: string;
  lastFilterDate: string;
  nextCareDate: string;
  nextCareBasis: string;
  usageStatus: "NORMAL" | "PARTIAL_STOP" | "TOTAL_STOP";
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
