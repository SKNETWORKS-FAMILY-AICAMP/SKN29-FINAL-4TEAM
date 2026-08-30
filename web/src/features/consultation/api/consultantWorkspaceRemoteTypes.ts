export type ConsultantInquiryStatusDto =
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
  | "CANCELLED";

export type ConsultantRiskLevelDto = "general" | "caution" | "danger";
export type ConsultantPriorityDto = "LOW" | "NORMAL" | "HIGH" | "URGENT";
export type ConsultantSortDto =
  | "UPDATED_DESC"
  | "UPDATED_ASC"
  | "WAITING_DESC"
  | "RISK_DESC";

export interface AllowedActionDto {
  code: string;
  label: string;
  operation_id: string;
  style: "PRIMARY" | "SECONDARY" | "DESTRUCTIVE";
  requires_confirmation: boolean;
  confirmation_message: string | null;
}

export interface ConsultantInquiryListItemDto {
  inquiry_id: string;
  inquiry_code: string;
  status: ConsultantInquiryStatusDto;
  state_version: number;
  risk_level: ConsultantRiskLevelDto;
  priority: ConsultantPriorityDto;
  symptom_summary: string;
  customer_display_name_masked: string;
  product_model: string;
  current_assignee_type: "CONSULTANT";
  received_at: string;
  updated_at: string;
  waiting_seconds: number;
  allowed_actions: readonly AllowedActionDto[];
}

export interface ConsultantInquiryListDataDto {
  items: readonly ConsultantInquiryListItemDto[];
  page_info: { page: number; size: number; total: number };
  status_counts: Partial<Record<ConsultantInquiryStatusDto, number>>;
}

export interface UnassignedConsultationQueueItemDto {
  inquiry_id: string;
  inquiry_code: string;
  status: "CONSULTATION_REQUIRED";
  state_version: number;
  risk_level: ConsultantRiskLevelDto;
  priority: ConsultantPriorityDto;
  symptom_summary: string;
  customer_display_name_masked: string;
  product_model: string;
  current_assignee_type: "NONE";
  received_at: string;
  updated_at: string;
  waiting_seconds: number;
  allowed_actions: readonly AllowedActionDto[];
}

export interface UnassignedConsultationQueueDataDto {
  items: readonly UnassignedConsultationQueueItemDto[];
  page_info: { page: number; size: number; total: number };
}

export interface ConsultantProductAndCareDto {
  product_model: string;
  product_model_name: string;
  subscription_status: string;
  management_type: string;
  recent_care_date: string | null;
}

export interface ConsultantSymptomAndQuestionnaireDto {
  symptom_summary: string;
  answers: readonly {
    question_code: string;
    question_text: string;
    answer: string;
  }[];
}

export interface ConsultantGuidanceAndActionsDto {
  usage_guidance_status:
    | "NORMAL"
    | "PARTIAL_STOP"
    | "TOTAL_STOP"
    | "PENDING_CONSULTATION"
    | null;
  usage_guidance_display_label:
    | "정상 사용 가능"
    | "일부 기능 사용 중단"
    | "제품 사용 중단"
    | "상담 확인 필요"
    | null;
  usage_guidance_message: string | null;
  restricted_functions: readonly string[];
}

export interface ConsultantVisitDetailDto {
  visit_id: string;
  inquiry_id: string;
  schedule: {
    preferred_date: string | null;
    confirmed_date: string | null;
    schedule_status:
      | "ASSIGNING"
      | "SCHEDULING"
      | "CONFIRMED"
      | "IN_PROGRESS"
      | "COMPLETED"
      | "FOLLOW_UP_REQUIRED"
      | "CANCELLED";
    synthetic_technician_id: string | null;
  };
  technician: {
    is_synthetic: true;
    technician_id: string;
    display_name: string;
    phone: string;
  } | null;
}

export interface ConsultantConsultationSummaryDto {
  ai_draft_summary: string | null;
  edited_summary: string | null;
  confirmed_summary: string | null;
  confirmed_at: string | null;
}

export interface ConsultantConsultationRecordDto {
  consultation_id: string;
  result_code:
    | "PENDING"
    | "COMPLETED_NO_VISIT"
    | "VISIT_REQUIRED"
    | "REOPENED_FOLLOWUP";
  summary: ConsultantConsultationSummaryDto;
  consultation_note: string | null;
  additional_check: string | null;
  customer_guidance: string | null;
  usage_guidance_status:
    | "NORMAL"
    | "PARTIAL_STOP"
    | "TOTAL_STOP"
    | "PENDING_CONSULTATION"
    | null;
}

export interface ConsultantStateHistoryDto {
  from_status: string | null;
  to_status: string;
  changed_at: string;
  actor_role: "CUSTOMER" | "CONSULTANT" | "TECHNICIAN" | "OPERATOR" | "SYSTEM";
}

export interface ConsultantWorkflowDto {
  status: ConsultantInquiryStatusDto;
  state_version: number;
  allowed_actions: readonly AllowedActionDto[];
}

export interface ConsultantSectionErrorDto {
  section: "product_and_care" | "consultation" | "visit";
  code: string;
  message: string;
}

export interface ConsultantInquiryDetailDto {
  inquiry: {
    inquiry_id: string;
    inquiry_code: string;
    status: ConsultantInquiryStatusDto;
    state_version: number;
    risk_level: ConsultantRiskLevelDto;
    priority: ConsultantPriorityDto;
    received_at: string;
    updated_at: string;
  };
  customer: {
    is_synthetic: true;
    display_name: string;
    phone: string;
    phone_masked: string;
    contact_phone: string | null;
  };
  product_and_care: ConsultantProductAndCareDto | null;
  symptom_and_questionnaire: ConsultantSymptomAndQuestionnaireDto;
  guidance_and_actions: ConsultantGuidanceAndActionsDto;
  consultation: ConsultantConsultationRecordDto | null;
  visit: ConsultantVisitDetailDto | null;
  state_history: readonly ConsultantStateHistoryDto[];
  workflow: ConsultantWorkflowDto;
  section_errors: readonly ConsultantSectionErrorDto[];
}

export interface ConsultantInquiryListQuery {
  q?: string;
  status?: readonly ConsultantInquiryStatusDto[];
  riskLevel?: readonly ConsultantRiskLevelDto[];
  priority?: readonly ConsultantPriorityDto[];
  from?: string;
  to?: string;
  sort?: ConsultantSortDto;
  page?: number;
  size?: number;
}

export interface UnassignedConsultationQueueQuery {
  q?: string;
  riskLevel?: readonly ConsultantRiskLevelDto[];
  priority?: readonly ConsultantPriorityDto[];
  from?: string;
  to?: string;
  sort?: ConsultantSortDto;
  page?: number;
  size?: number;
}
