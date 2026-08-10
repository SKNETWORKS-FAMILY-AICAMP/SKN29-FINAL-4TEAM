import type { ApiResponse } from "../../../common/api/apiResponse";
import {
  requestApi,
  type ApiRequestOptions,
} from "../../../common/api/httpClient";
import type { RequestContext } from "../../../common/api/requestContext";
import type {
  AllowedActionDto,
  ConsultantInquiryStatusDto,
} from "../../consultation/api/consultantWorkspaceRemoteTypes";

export interface VisitHandoffDto {
  product_summary: string;
  symptom_summary: string;
  action_summary: string;
  risk_summary: string;
  priority_check_items: string[];
  consultant_final: string;
}

export interface VisitReviewRequestDto {
  state_version: number;
  reason_code:
    | "REMOTE_RESOLUTION_LIMITED"
    | "SAFETY_CHECK_REQUIRED"
    | "REPEATED_SYMPTOM"
    | "PHYSICAL_INSPECTION_REQUIRED";
  reason_detail?: string | null;
}

export interface CreateVisitRequestDto {
  state_version: number;
  visit_reason: string;
  preferred_date?: string | null;
  usage_guidance_status:
    | "NORMAL"
    | "PARTIAL_STOP"
    | "TOTAL_STOP"
    | "PENDING_CONSULTATION";
  handoff: VisitHandoffDto;
}

export interface UpdateVisitScheduleRequestDto {
  state_version: number;
  synthetic_technician_id: string;
  preferred_date: string | null;
  confirmed_date: string | null;
}

export interface ConfirmVisitRequestDto {
  state_version: number;
}

export interface VisitTransitionResultDto {
  message: string;
  inquiry_id: string;
  status: ConsultantInquiryStatusDto;
  state_version: number;
  allowed_actions: AllowedActionDto[];
  idempotent_replay: boolean;
  resource?: Record<string, unknown> | null;
}

export type VisitWriteRequester = <TData>(
  path: string,
  options: ApiRequestOptions,
) => Promise<ApiResponse<TData>>;

export interface VisitWriteRepository {
  requestReview(
    inquiryId: string,
    body: VisitReviewRequestDto,
    context: RequestContext,
  ): Promise<ApiResponse<VisitTransitionResultDto>>;
  create(
    inquiryId: string,
    body: CreateVisitRequestDto,
    context: RequestContext,
  ): Promise<ApiResponse<VisitTransitionResultDto>>;
  saveSchedule(
    visitId: string,
    body: UpdateVisitScheduleRequestDto,
    context: RequestContext,
  ): Promise<ApiResponse<VisitTransitionResultDto>>;
  confirm(
    visitId: string,
    body: ConfirmVisitRequestDto,
    context: RequestContext,
  ): Promise<ApiResponse<VisitTransitionResultDto>>;
}

const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

export function toNullableDateOnly(value: string): string | null {
  const normalized = value.trim();
  if (!normalized) return null;
  if (!DATE_ONLY_PATTERN.test(normalized)) {
    throw new RangeError("방문 날짜는 YYYY-MM-DD 형식이어야 합니다.");
  }
  return normalized;
}

export function buildVisitScheduleRequest(input: {
  stateVersion: number;
  technicianId: string;
  preferredDate: string;
  confirmedDate: string;
}): UpdateVisitScheduleRequestDto {
  return {
    state_version: input.stateVersion,
    synthetic_technician_id: input.technicianId,
    preferred_date: toNullableDateOnly(input.preferredDate),
    confirmed_date: toNullableDateOnly(input.confirmedDate),
  };
}

function writeOptions(
  method: "POST" | "PATCH",
  body: unknown,
  requestContext: RequestContext,
): ApiRequestOptions {
  return { method, body, requestContext };
}

export function createRemoteVisitWriteRepository(
  requester: VisitWriteRequester = requestApi,
): VisitWriteRepository {
  const inquiryPath = (id: string) =>
    `/inquiries/${encodeURIComponent(id)}`;
  const visitPath = (id: string) => `/visits/${encodeURIComponent(id)}`;

  return {
    requestReview: (inquiryId, body, context) =>
      requester<VisitTransitionResultDto>(
        `${inquiryPath(inquiryId)}/visit-review`,
        writeOptions("POST", body, context),
      ),
    create: (inquiryId, body, context) =>
      requester<VisitTransitionResultDto>(
        `${inquiryPath(inquiryId)}/visits`,
        writeOptions("POST", body, context),
      ),
    saveSchedule: (visitId, body, context) =>
      requester<VisitTransitionResultDto>(
        `${visitPath(visitId)}/schedule`,
        writeOptions("PATCH", body, context),
      ),
    confirm: (visitId, body, context) =>
      requester<VisitTransitionResultDto>(
        `${visitPath(visitId)}/confirm`,
        writeOptions("POST", body, context),
      ),
  };
}

