import type { ApiResponse } from "../../../common/api/apiResponse";
import {
  requestApi,
  type ApiRequestOptions,
} from "../../../common/api/httpClient";
import type { RequestContext } from "../../../common/api/requestContext";
import type {
  AllowedActionDto,
  ConsultantConsultationRecordDto,
  ConsultantInquiryStatusDto,
} from "../api/consultantWorkspaceRemoteTypes";

export interface StateTransitionRequestDto {
  state_version: number;
}

export interface SaveConsultationRequestDto extends StateTransitionRequestDto {
  summary?: string;
  consultation_note?: string;
  additional_check?: string;
  customer_guidance?: string;
  result_code?:
    | "PENDING"
    | "COMPLETED_NO_VISIT"
    | "VISIT_REQUIRED"
    | "REOPENED_FOLLOWUP";
  usage_guidance_status?:
    | "NORMAL"
    | "PARTIAL_STOP"
    | "TOTAL_STOP"
    | "PENDING_CONSULTATION";
}

export type CompleteConsultationRequestDto = StateTransitionRequestDto;

export type CancelInquiryReasonCode =
  | "CUSTOMER_REQUEST"
  | "DUPLICATE_INQUIRY"
  | "ISSUE_RESOLVED"
  | "OTHER";

export interface CancelInquiryRequestDto extends StateTransitionRequestDto {
  reason_code: CancelInquiryReasonCode;
  reason_detail?: string | null;
}

export interface CancelInquiryResultDto {
  inquiry_id: string;
  state: "CANCELLED";
  state_version: number;
  idempotent_replay: boolean;
  allowed_actions: AllowedActionDto[];
}

export interface StateTransitionResultDto {
  message: string;
  inquiry_id: string;
  status: ConsultantInquiryStatusDto;
  state_version: number;
  allowed_actions: AllowedActionDto[];
  idempotent_replay: boolean;
  resource: ConsultantConsultationRecordDto | null;
}

export type ConsultationWriteRequester = <TData>(
  path: string,
  options: ApiRequestOptions,
) => Promise<ApiResponse<TData>>;

export interface ConsultationWriteRepository {
  cancel(
    inquiryId: string,
    body: CancelInquiryRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<CancelInquiryResultDto>>;
  claimConsultation(
    inquiryId: string,
    body: StateTransitionRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<StateTransitionResultDto>>;
  start(
    inquiryId: string,
    body: StateTransitionRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<StateTransitionResultDto>>;
  saveSummary(
    inquiryId: string,
    body: SaveConsultationRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<StateTransitionResultDto>>;
  confirmSummary(
    inquiryId: string,
    body: StateTransitionRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<StateTransitionResultDto>>;
  complete(
    inquiryId: string,
    body: CompleteConsultationRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<StateTransitionResultDto>>;
  resume(
    inquiryId: string,
    body: StateTransitionRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<StateTransitionResultDto>>;
  finalize(
    inquiryId: string,
    body: StateTransitionRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<StateTransitionResultDto>>;
}

function createWriteRequest(
  method: "POST" | "PATCH",
  body: unknown,
  requestContext: RequestContext,
): ApiRequestOptions {
  return { method, body, requestContext };
}

export function createRemoteConsultationWriteRepository(
  requester: ConsultationWriteRequester = requestApi,
): ConsultationWriteRepository {
  const inquiryPath = (inquiryId: string) =>
    `/inquiries/${encodeURIComponent(inquiryId)}`;

  return {
    cancel: (inquiryId, body, requestContext) =>
      requester<CancelInquiryResultDto>(
        `${inquiryPath(inquiryId)}/cancel`,
        createWriteRequest("POST", body, requestContext),
      ),
    claimConsultation: (inquiryId, body, requestContext) =>
      requester<StateTransitionResultDto>(
        `${inquiryPath(inquiryId)}/claim-consultation`,
        createWriteRequest("POST", body, requestContext),
      ),
    start: (inquiryId, body, requestContext) =>
      requester<StateTransitionResultDto>(
        `${inquiryPath(inquiryId)}/start-consultation`,
        createWriteRequest("POST", body, requestContext),
      ),
    saveSummary: (inquiryId, body, requestContext) =>
      requester<StateTransitionResultDto>(
        `${inquiryPath(inquiryId)}/consultation-summary`,
        createWriteRequest("PATCH", body, requestContext),
      ),
    confirmSummary: (inquiryId, body, requestContext) =>
      requester<StateTransitionResultDto>(
        `${inquiryPath(inquiryId)}/consultation-summary/confirm`,
        createWriteRequest("POST", body, requestContext),
      ),
    complete: (inquiryId, body, requestContext) =>
      requester<StateTransitionResultDto>(
        `${inquiryPath(inquiryId)}/complete-consultation`,
        createWriteRequest("POST", body, requestContext),
      ),
    resume: (inquiryId, body, requestContext) =>
      requester<StateTransitionResultDto>(
        `${inquiryPath(inquiryId)}/resume-consultation`,
        createWriteRequest("POST", body, requestContext),
      ),
    finalize: (inquiryId, body, requestContext) =>
      requester<StateTransitionResultDto>(
        `${inquiryPath(inquiryId)}/finalize`,
        createWriteRequest("POST", body, requestContext),
      ),
  };
}
