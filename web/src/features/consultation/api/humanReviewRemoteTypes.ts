import type { ConsultantInquiryStatusDto } from "./consultantWorkspaceRemoteTypes";

export interface HumanReviewGuidanceItemDto {
  step_no: number;
  instruction_text: string;
  caution_text: string | null;
  requires_confirmation: boolean;
}

export interface HumanReviewGuidanceDto {
  guidance_id: string;
  guidance_version: number;
  title: string;
  summary_text: string;
  safety_notice: string | null;
  requires_consultation: boolean;
  items: HumanReviewGuidanceItemDto[];
}

export interface HumanReviewDto {
  review_id: string;
  inquiry_id: string;
  inquiry_status: ConsultantInquiryStatusDto;
  inquiry_state_version: number;
  model_code: string;
  status: "PENDING" | "APPROVED" | "MODIFIED" | "REJECTED" | "RESUME_FAILED";
  decision: "APPROVE" | "MODIFY" | "REJECT" | null;
  review_state_version: number;
  source_inquiry_state_version: number;
  reason_code: string;
  original_requires_consultation: boolean;
  proposed_guidance: HumanReviewGuidanceDto;
  allowed_actions: string[];
  idempotent_replay?: boolean;
}

export interface HumanReviewListDataDto {
  items: HumanReviewDto[];
}

export interface HumanReviewDecisionRequestDto {
  decision: "APPROVE";
  review_state_version: number;
  reason_code: "APPROVED_AS_IS";
  consultation_disposition: "PRESERVE" | "REQUIRE";
  consultation_reason_code?: "PRODUCT_FUNCTION_UNCERTAIN";
}
