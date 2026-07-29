import type { InquiryId } from "../../../entities/inquiry/inquiryIdentifiers";
import type {
  CounselorInquiry,
  CounselorRisk,
  CounselorStatus,
} from "../../consultation/model/consultantWorkspaceTypes";

export interface OperationsFilters {
  assignee: "ALL" | string;
  managementType: "ALL" | string;
  productModel: "ALL" | string;
  receivedFrom: string;
  receivedTo: string;
  result: "ALL" | "RESOLVED" | "IN_PROGRESS";
  risk: "ALL" | CounselorRisk;
  status: "ALL" | CounselorStatus;
  symptom: "ALL" | string;
}

export interface OperationsMetric {
  key: "TOTAL" | "DANGER" | "CONSULTATION" | "VISIT" | "RESOLVED";
  label: string;
  count: number;
  description: string;
  tone: "default" | "danger" | "warning" | "success" | "info";
}

export interface OperationsDistributionItem {
  key: string;
  label: string;
  count: number;
  percent: number;
}

export type OperationsExceptionCode =
  | "CARE_SCHEDULE_MISSING"
  | "QUESTIONNAIRE_UNANSWERED"
  | "PROCESS_DELAY"
  | "EVIDENCE_SEARCH_FAILED"
  | "AI_PROCESS_FAILED";

export interface OperationsExceptionItem {
  inquiryId: InquiryId;
  inquiryCode: string;
  symptomLabel: string;
  reasons: readonly {
    code: OperationsExceptionCode;
    label: string;
  }[];
  lastStep: string;
  assignee: string;
  updatedAt: string;
  risk: CounselorRisk;
}

export interface OperationsDashboardSummary {
  inquiries: readonly CounselorInquiry[];
  metrics: readonly OperationsMetric[];
  symptomDistribution: readonly OperationsDistributionItem[];
  statusDistribution: readonly OperationsDistributionItem[];
  exceptions: readonly OperationsExceptionItem[];
}
