import type {
  AllowedActionDto,
  ConsultantInquiryDetailDto,
  ConsultantInquiryListDataDto,
  ConsultantInquiryStatusDto,
  ConsultantPriorityDto,
  ConsultantRiskLevelDto,
  UnassignedConsultationQueueDataDto,
} from "../api/consultantWorkspaceRemoteTypes";

export interface RemoteAllowedAction {
  code: string;
  label: string;
  operationId: string;
  style: "PRIMARY" | "SECONDARY" | "DESTRUCTIVE";
  requiresConfirmation: boolean;
  confirmationMessage: string | null;
}

export interface ConsultantInquiryListItemViewModel {
  inquiryId: string;
  inquiryCode: string;
  status: ConsultantInquiryStatusDto;
  stateVersion: number;
  riskLevel: ConsultantRiskLevelDto;
  priority: ConsultantPriorityDto;
  symptomSummary: string;
  customerDisplayNameMasked: string;
  productModel: string;
  receivedAt: string;
  updatedAt: string;
  waitingSeconds: number;
  allowedActions: readonly RemoteAllowedAction[];
}

export interface ConsultantInquiryListViewModel {
  items: readonly ConsultantInquiryListItemViewModel[];
  pageInfo: { page: number; size: number; total: number };
  statusCounts: Partial<Record<ConsultantInquiryStatusDto, number>>;
}

export interface UnassignedConsultationQueueItemViewModel {
  inquiryId: string;
  inquiryCode: string;
  status: "CONSULTATION_REQUIRED";
  stateVersion: number;
  riskLevel: ConsultantRiskLevelDto;
  priority: ConsultantPriorityDto;
  symptomSummary: string;
  customerDisplayNameMasked: string;
  productModel: string;
  currentAssigneeType: "NONE";
  receivedAt: string;
  updatedAt: string;
  waitingSeconds: number;
  allowedActions: readonly RemoteAllowedAction[];
}

export interface UnassignedConsultationQueueViewModel {
  items: readonly UnassignedConsultationQueueItemViewModel[];
  pageInfo: { page: number; size: number; total: number };
}

export interface ConsultantInquiryDetailViewModel {
  inquiryId: string;
  inquiryCode: string;
  status: ConsultantInquiryStatusDto;
  stateVersion: number;
  riskLevel: ConsultantRiskLevelDto;
  priority: ConsultantPriorityDto;
  receivedAt: string;
  updatedAt: string;
  customer: { isSynthetic: true; displayName: string; phoneMasked: string };
  productAndCare: {
    productModel: string;
    productModelName: string;
    subscriptionStatus: string;
    managementType: string;
    recentCareDate: string | null;
  } | null;
  symptomAndQuestionnaire: {
    symptomSummary: string;
    answers: readonly {
      questionCode: string;
      questionText: string;
      answer: string;
    }[];
  };
  guidanceAndActions: {
    usageGuidanceStatus:
      | "NORMAL"
      | "PARTIAL_STOP"
      | "TOTAL_STOP"
      | "PENDING_CONSULTATION"
      | null;
    usageGuidanceDisplayLabel:
      | "정상 사용 가능"
      | "일부 기능 사용 중단"
      | "제품 사용 중단"
      | "상담 확인 필요"
      | null;
    usageGuidanceMessage: string | null;
    restrictedFunctions: readonly string[];
  };
  consultation: {
    consultationId: string;
    resultCode:
      | "PENDING"
      | "COMPLETED_NO_VISIT"
      | "VISIT_REQUIRED"
      | "REOPENED_FOLLOWUP";
    summary: {
      aiDraftSummary: string | null;
      editedSummary: string | null;
      confirmedSummary: string | null;
      confirmedAt: string | null;
    };
    consultationNote: string | null;
    additionalCheck: string | null;
    customerGuidance: string | null;
    usageGuidanceStatus:
      | "NORMAL"
      | "PARTIAL_STOP"
      | "TOTAL_STOP"
      | "PENDING_CONSULTATION"
      | null;
  } | null;
  visit: {
    visitId: string;
    inquiryId: string;
    schedule: {
      preferredDate: string | null;
      confirmedDate: string | null;
      scheduleStatus:
        | "ASSIGNING"
        | "SCHEDULING"
        | "CONFIRMED"
        | "IN_PROGRESS"
        | "COMPLETED"
        | "FOLLOW_UP_REQUIRED"
        | "CANCELLED";
      syntheticTechnicianId: string | null;
    };
    technician: {
      isSynthetic: true;
      technicianId: string;
      displayName: string;
      phone: string;
    } | null;
  } | null;
  stateHistory: readonly {
    fromStatus: string | null;
    toStatus: string;
    changedAt: string;
    actorRole: "CUSTOMER" | "CONSULTANT" | "TECHNICIAN" | "OPERATOR" | "SYSTEM";
  }[];
  workflow: {
    status: ConsultantInquiryStatusDto;
    stateVersion: number;
    allowedActions: readonly RemoteAllowedAction[];
  };
  sectionErrors: readonly {
    section: "product_and_care" | "consultation" | "visit";
    code: string;
    message: string;
  }[];
}

function mapAllowedAction(dto: AllowedActionDto): RemoteAllowedAction {
  return {
    code: dto.code,
    label: dto.label,
    operationId: dto.operation_id,
    style: dto.style,
    requiresConfirmation: dto.requires_confirmation,
    confirmationMessage: dto.confirmation_message,
  };
}

const MANAGEMENT_TYPE_LABELS: Readonly<Record<string, string>> = {
  VISIT: "방문 관리",
  VISIT_CARE: "방문 관리",
  SELF: "자가 관리",
  SELF_CARE: "자가 관리",
};

const SUBSCRIPTION_STATUS_LABELS: Readonly<Record<string, string>> = {
  ACTIVE: "이용 중",
  PAUSED: "일시 정지",
  CANCELLED: "해지",
  EXPIRED: "만료",
};

export function getManagementTypeLabel(value: string): string {
  return MANAGEMENT_TYPE_LABELS[value] ?? value;
}

export function getSubscriptionStatusLabel(value: string): string {
  return SUBSCRIPTION_STATUS_LABELS[value] ?? value;
}

export function mapConsultantInquiryList(
  dto: ConsultantInquiryListDataDto,
): ConsultantInquiryListViewModel {
  return {
    items: dto.items.map((item) => ({
      inquiryId: item.inquiry_id,
      inquiryCode: item.inquiry_code,
      status: item.status,
      stateVersion: item.state_version,
      riskLevel: item.risk_level,
      priority: item.priority,
      symptomSummary: item.symptom_summary,
      customerDisplayNameMasked: item.customer_display_name_masked,
      productModel: item.product_model,
      receivedAt: item.received_at,
      updatedAt: item.updated_at,
      waitingSeconds: item.waiting_seconds,
      allowedActions: item.allowed_actions.map(mapAllowedAction),
    })),
    pageInfo: { ...dto.page_info },
    statusCounts: dto.status_counts,
  };
}

export function mapUnassignedConsultationQueue(
  dto: UnassignedConsultationQueueDataDto,
): UnassignedConsultationQueueViewModel {
  return {
    items: dto.items.map((item) => ({
      inquiryId: item.inquiry_id,
      inquiryCode: item.inquiry_code,
      status: item.status,
      stateVersion: item.state_version,
      riskLevel: item.risk_level,
      priority: item.priority,
      symptomSummary: item.symptom_summary,
      customerDisplayNameMasked: item.customer_display_name_masked,
      productModel: item.product_model,
      currentAssigneeType: item.current_assignee_type,
      receivedAt: item.received_at,
      updatedAt: item.updated_at,
      waitingSeconds: item.waiting_seconds,
      allowedActions: item.allowed_actions.map(mapAllowedAction),
    })),
    pageInfo: { ...dto.page_info },
  };
}

export function mapConsultantInquiryDetail(
  dto: ConsultantInquiryDetailDto,
): ConsultantInquiryDetailViewModel {
  const { inquiry, customer } = dto;
  return {
    inquiryId: inquiry.inquiry_id,
    inquiryCode: inquiry.inquiry_code,
    status: inquiry.status,
    stateVersion: inquiry.state_version,
    riskLevel: inquiry.risk_level,
    priority: inquiry.priority,
    receivedAt: inquiry.received_at,
    updatedAt: inquiry.updated_at,
    customer: {
      isSynthetic: customer.is_synthetic,
      displayName: customer.display_name,
      phoneMasked: customer.phone_masked,
    },
    productAndCare: dto.product_and_care
      ? {
          productModel: dto.product_and_care.product_model,
          productModelName: dto.product_and_care.product_model_name,
          subscriptionStatus: dto.product_and_care.subscription_status,
          managementType: dto.product_and_care.management_type,
          recentCareDate: dto.product_and_care.recent_care_date,
        }
      : null,
    symptomAndQuestionnaire: {
      symptomSummary: dto.symptom_and_questionnaire.symptom_summary,
      answers: dto.symptom_and_questionnaire.answers.map((answer) => ({
        questionCode: answer.question_code,
        questionText: answer.question_text,
        answer: answer.answer,
      })),
    },
    guidanceAndActions: {
      usageGuidanceStatus: dto.guidance_and_actions.usage_guidance_status,
      usageGuidanceDisplayLabel:
        dto.guidance_and_actions.usage_guidance_display_label,
      usageGuidanceMessage: dto.guidance_and_actions.usage_guidance_message,
      restrictedFunctions: dto.guidance_and_actions.restricted_functions,
    },
    consultation: dto.consultation
      ? {
          consultationId: dto.consultation.consultation_id,
          resultCode: dto.consultation.result_code,
          summary: {
            aiDraftSummary: dto.consultation.summary.ai_draft_summary,
            editedSummary: dto.consultation.summary.edited_summary,
            confirmedSummary: dto.consultation.summary.confirmed_summary,
            confirmedAt: dto.consultation.summary.confirmed_at,
          },
          consultationNote: dto.consultation.consultation_note,
          additionalCheck: dto.consultation.additional_check,
          customerGuidance: dto.consultation.customer_guidance,
          usageGuidanceStatus: dto.consultation.usage_guidance_status,
        }
      : null,
    visit: dto.visit
      ? {
          visitId: dto.visit.visit_id,
          inquiryId: dto.visit.inquiry_id,
          schedule: {
            preferredDate: dto.visit.schedule.preferred_date,
            confirmedDate: dto.visit.schedule.confirmed_date,
            scheduleStatus: dto.visit.schedule.schedule_status,
            syntheticTechnicianId:
              dto.visit.schedule.synthetic_technician_id,
          },
          technician: dto.visit.technician
            ? {
                isSynthetic: dto.visit.technician.is_synthetic,
                technicianId: dto.visit.technician.technician_id,
                displayName: dto.visit.technician.display_name,
                phone: dto.visit.technician.phone,
              }
            : null,
        }
      : null,
    stateHistory: dto.state_history.map((history) => ({
      fromStatus: history.from_status,
      toStatus: history.to_status,
      changedAt: history.changed_at,
      actorRole: history.actor_role,
    })),
    workflow: {
      status: dto.workflow.status,
      stateVersion: dto.workflow.state_version,
      allowedActions: dto.workflow.allowed_actions.map(mapAllowedAction),
    },
    sectionErrors: dto.section_errors.map((error) => ({
      section: error.section,
      code: error.code,
      message: error.message,
    })),
  };
}
