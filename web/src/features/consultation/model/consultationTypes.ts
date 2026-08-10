import type {
  CounselorActionCode,
  CounselorInquiry,
  CounselorStatus,
} from "./consultantWorkspaceTypes";
import type {
  WorkflowActionSuccess,
  WorkflowConflict,
} from "../../workflow-action/model/workflowActionMapper";

export type ConsultationMockScenario =
  | "SUCCESS"
  | "FORBIDDEN"
  | "CONFLICT"
  | "DUPLICATE_EVENT"
  | "VALIDATION_ERROR"
  | "NETWORK_ERROR";

export type VisitRequiredValue = "UNDECIDED" | "REQUIRED" | "NOT_REQUIRED";

export interface ConsultationFormValues {
  consultationNote: string;
  additionalCheck: string;
  customerGuidance: string;
  consultationResult: string;
  summaryRevision: string;
  summaryConfirmed: boolean;
  visitRequired: VisitRequiredValue;
  usageStatus: CounselorInquiry["usageStatus"];
}

export type ConsultationField = keyof ConsultationFormValues;
export type ConsultationFieldErrors = Partial<
  Record<ConsultationField, string>
>;

// 상담 API request schema가 확정되기 전까지만 사용하는 교체 가능한 Mock DTO입니다.
export interface ProvisionalConsultationActionRequest {
  inquiry_id: string;
  action_code: CounselorActionCode;
  operation_id: string;
  state_version: number;
  consultation_note: string;
  additional_check: string;
  customer_guidance: string;
  consultation_result: string;
  summary_revision: string;
  summary_confirmed: boolean;
  visit_required: VisitRequiredValue;
  usage_guidance_status: CounselorInquiry["usageStatus"];
  idempotency_key: string;
  correlation_id: string;
}

export type ConsultationActionSuccess =
  WorkflowActionSuccess<CounselorActionCode> & {
    status: CounselorStatus;
  };

export type ConsultationActionErrorKind =
  | "FORBIDDEN"
  | "RUNTIME_BLOCKED"
  | "VALIDATION_ERROR"
  | "NETWORK_ERROR";

interface ConsultationNonConflictErrorDetails {
  kind: ConsultationActionErrorKind;
  message: string;
  fieldErrors?: ConsultationFieldErrors;
  correlationId?: string;
}

export type ConsultationActionErrorDetails =
  | ConsultationNonConflictErrorDetails
  | WorkflowConflict<CounselorActionCode, CounselorInquiry["status"]>;

