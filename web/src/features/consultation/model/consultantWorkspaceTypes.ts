export type CounselorRisk = "GENERAL" | "CAUTION" | "DANGER";

export type CounselorStatus =
  | "QUESTIONNAIRE_IN_PROGRESS"
  | "CONSULTATION_REQUIRED"
  | "CONSULTATION_IN_PROGRESS"
  | "VISIT_SCHEDULED"
  | "COMPLETION_PENDING";

export type CounselorPriority = "NORMAL" | "HIGH" | "URGENT";

export type DetailTab = "summary" | "answers" | "evidence" | "timeline";

export interface CounselorEvidence {
  documentTitle: string;
  summary: string;
  evidenceId: string;
  chunkId: string;
  documentId: string;
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
  evidence: readonly CounselorEvidence[];
  timeline: readonly CounselorTimelineItem[];
}

export interface CounselorFilters {
  query: string;
  status: "ALL" | CounselorStatus;
  risk: "ALL" | CounselorRisk;
  consultation: "ALL" | "REQUIRED" | "FINAL";
}
