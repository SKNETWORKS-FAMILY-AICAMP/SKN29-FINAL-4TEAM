import { appEnv, type MockDataset } from "../../../app/config/env";
import { ApiClientError } from "../../../common/api/apiError";
import type { ApiResponse } from "../../../common/api/apiResponse";
import { requestApi } from "../../../common/api/httpClient";
import {
  maskCustomerName,
  maskCustomerPhone,
} from "../../../common/privacy/customerPrivacy";
import {
  CONSULTANT_QUEUE_INQUIRIES,
  REMOTE_PARITY_CONSULTANT_INQUIRIES,
  REMOTE_PARITY_UNASSIGNED_CONSULTANT_INQUIRIES,
  UNASSIGNED_CONSULTANT_INQUIRIES,
} from "../model/consultantWorkspaceMock";
import {
  mapConsultantInquiryDetail,
  mapConsultantInquiryList,
  mapUnassignedConsultationQueue,
  type ConsultantInquiryDetailViewModel,
  type ConsultantInquiryListViewModel,
  type UnassignedConsultationQueueViewModel,
} from "../model/consultantWorkspaceRemoteMapper";
import type {
  AllowedActionDto,
  ConsultantInquiryDetailDto,
  ConsultantInquiryListDataDto,
  ConsultantInquiryListQuery,
  ConsultantInquiryStatusDto,
  UnassignedConsultationQueueDataDto,
  UnassignedConsultationQueueItemDto,
  UnassignedConsultationQueueQuery,
} from "../api/consultantWorkspaceRemoteTypes";
import type { CounselorInquiry } from "../model/consultantWorkspaceTypes";

export interface RepositoryResult<T> {
  data: T;
  correlationId: string;
}

export interface ConsultantWorkspaceDataRepository {
  readonly dataSource: "MOCK" | "REMOTE";
  listInquiries(
    query?: ConsultantInquiryListQuery,
  ): Promise<RepositoryResult<ConsultantInquiryListViewModel>>;
  listUnassignedConsultations(
    query?: UnassignedConsultationQueueQuery,
  ): Promise<RepositoryResult<UnassignedConsultationQueueViewModel>>;
  getInquiryDetail(
    inquiryId: string,
  ): Promise<RepositoryResult<ConsultantInquiryDetailViewModel>>;
}

export type ConsultantApiRequester = <TData>(
  path: string,
) => Promise<ApiResponse<TData>>;

function getMockInquiries(
  dataset: MockDataset = appEnv.mockDataset,
): readonly CounselorInquiry[] {
  return dataset === "DESIGN_SCENARIOS"
    ? CONSULTANT_QUEUE_INQUIRIES
    : REMOTE_PARITY_CONSULTANT_INQUIRIES;
}

function requireResponseData<TData>(response: ApiResponse<TData>): TData {
  if (response.data === null) {
    throw new ApiClientError({
      kind: "PARSE_ERROR",
      message: "성공 응답에 data가 없습니다.",
      correlationId: response.metadata.correlation_id,
    });
  }
  return response.data;
}

export function buildConsultantInquiryListPath(
  query: ConsultantInquiryListQuery = {},
): string {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  query.status?.forEach((value) => params.append("status", value));
  query.riskLevel?.forEach((value) => params.append("risk_level", value));
  query.priority?.forEach((value) => params.append("priority", value));
  if (query.from) params.set("from", query.from);
  if (query.to) params.set("to", query.to);
  if (query.sort) params.set("sort", query.sort);
  if (query.page !== undefined) params.set("page", String(query.page));
  if (query.size !== undefined) params.set("size", String(query.size));
  const queryString = params.toString();
  return `/inquiries${queryString ? `?${queryString}` : ""}`;
}

const USAGE_GUIDANCE_DISPLAY_LABELS = {
  NORMAL: "정상 사용 가능",
  PARTIAL_STOP: "일부 기능 사용 중단",
  TOTAL_STOP: "제품 사용 중단",
  PENDING_CONSULTATION: "상담 확인 필요",
} as const;

function getMockUnassignedInquiries(
  dataset: MockDataset = appEnv.mockDataset,
): readonly CounselorInquiry[] {
  return dataset === "DESIGN_SCENARIOS"
    ? UNASSIGNED_CONSULTANT_INQUIRIES
    : REMOTE_PARITY_UNASSIGNED_CONSULTANT_INQUIRIES;
}

export function buildUnassignedConsultationQueuePath(
  query: UnassignedConsultationQueueQuery = {},
): string {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  query.riskLevel?.forEach((value) => params.append("risk_level", value));
  query.priority?.forEach((value) => params.append("priority", value));
  if (query.from) params.set("from", query.from);
  if (query.to) params.set("to", query.to);
  if (query.sort) params.set("sort", query.sort);
  if (query.page !== undefined) params.set("page", String(query.page));
  if (query.size !== undefined) params.set("size", String(query.size));
  const queryString = params.toString();
  return `/inquiries/unassigned-consultations${
    queryString ? `?${queryString}` : ""
  }`;
}

export function createRemoteConsultantWorkspaceDataRepository(
  requester: ConsultantApiRequester = requestApi,
): ConsultantWorkspaceDataRepository {
  return {
    dataSource: "REMOTE",
    async listInquiries(query) {
      const response = await requester<ConsultantInquiryListDataDto>(
        buildConsultantInquiryListPath(query),
      );
      return {
        data: mapConsultantInquiryList(requireResponseData(response)),
        correlationId: response.metadata.correlation_id,
      };
    },
    async listUnassignedConsultations(query) {
      const response = await requester<UnassignedConsultationQueueDataDto>(
        buildUnassignedConsultationQueuePath(query),
      );
      return {
        data: mapUnassignedConsultationQueue(requireResponseData(response)),
        correlationId: response.metadata.correlation_id,
      };
    },
    async getInquiryDetail(inquiryId) {
      const response = await requester<ConsultantInquiryDetailDto>(
        `/inquiries/${encodeURIComponent(inquiryId)}`,
      );
      return {
        data: mapConsultantInquiryDetail(requireResponseData(response)),
        correlationId: response.metadata.correlation_id,
      };
    },
  };
}

function toStatus(value: CounselorInquiry["status"]): ConsultantInquiryStatusDto {
  if (value === "UNKNOWN") {
    throw new ApiClientError({
      kind: "PARSE_ERROR",
      message: "Mock 문의 상태를 API 계약 상태로 바꿀 수 없습니다.",
    });
  }
  return value;
}

function toAllowedActionDto(
  action: CounselorInquiry["allowedActions"][number],
): AllowedActionDto {
  return {
    code: action.code,
    label: action.label,
    operation_id: action.operationId,
    style: action.style,
    requires_confirmation: action.requiresConfirmation,
    confirmation_message: action.confirmationMessage,
  };
}

function toMockListItem(inquiry: CounselorInquiry) {
  if (inquiry.riskLevel === "UNKNOWN" || inquiry.priority === "UNKNOWN") {
    throw new ApiClientError({
      kind: "PARSE_ERROR",
      message: "Mock 문의의 위험도 또는 우선순위를 API 계약 값으로 바꿀 수 없습니다.",
    });
  }
  return {
    inquiry_id: inquiry.inquiryId,
    inquiry_code: inquiry.inquiryCode,
    status: toStatus(inquiry.status),
    state_version: inquiry.stateVersion,
    risk_level: inquiry.riskLevel.toLowerCase() as "general" | "caution" | "danger",
    priority: inquiry.priority,
    symptom_summary: inquiry.customerMessage,
    customer_display_name_masked: maskCustomerName(inquiry.customerDisplayName),
    product_model: inquiry.manualModel,
    current_assignee_type: "CONSULTANT" as const,
    received_at: inquiry.createdAt,
    updated_at: inquiry.updatedAt,
    waiting_seconds: inquiry.waitingMinutes * 60,
    allowed_actions: inquiry.allowedActions.map(toAllowedActionDto),
  };
}

function toMockUnassignedQueueItem(
  inquiry: CounselorInquiry,
): UnassignedConsultationQueueItemDto {
  const item = toMockListItem(inquiry);
  return {
    ...item,
    status: "CONSULTATION_REQUIRED",
    current_assignee_type: "NONE",
    allowed_actions: [
      {
        code: "CLAIM_CONSULTATION",
        label: "상담 배정받기",
        operation_id: "claimConsultation",
        style: "PRIMARY",
        requires_confirmation: false,
        confirmation_message: null,
      },
    ],
  };
}

function matchesMockQuery(
  inquiry: CounselorInquiry,
  query: ConsultantInquiryListQuery,
): boolean {
  const q = query.q?.trim().toLowerCase();
  if (
    q &&
    ![inquiry.inquiryCode, inquiry.customerDisplayName, inquiry.customerMessage]
      .join(" ")
      .toLowerCase()
      .includes(q)
  ) return false;
  if (query.status?.length && !query.status.includes(toStatus(inquiry.status))) return false;
  if (
    query.riskLevel?.length &&
    !query.riskLevel.includes(
      inquiry.riskLevel.toLowerCase() as "general" | "caution" | "danger",
    )
  ) return false;
  if (
    query.priority?.length &&
    inquiry.priority !== "UNKNOWN" &&
    !query.priority.includes(inquiry.priority)
  ) return false;
  if (query.from && inquiry.createdAt.slice(0, 10) < query.from) return false;
  if (query.to && inquiry.createdAt.slice(0, 10) > query.to) return false;
  return true;
}

export function createMockConsultantWorkspaceDataRepository(
  dataset: MockDataset = appEnv.mockDataset,
): ConsultantWorkspaceDataRepository {
  const mockInquiries = getMockInquiries(dataset);
  return {
    dataSource: "MOCK",
    async listInquiries(query = {}) {
      return {
        data: createMockConsultantInquiryListViewModel(query, dataset),
        correlationId: "mock-consultant-workspace",
      };
    },
    async listUnassignedConsultations(query = {}) {
      return {
        data: createMockUnassignedConsultationQueueViewModel(query, dataset),
        correlationId: "mock-consultant-workspace",
      };
    },
    async getInquiryDetail(inquiryId) {
      const inquiry = mockInquiries.find(
        (item) => item.inquiryId === inquiryId,
      );
      if (!inquiry) {
        throw new ApiClientError({
          kind: "NOT_FOUND",
          status: 404,
          message: "Mock 문의를 찾을 수 없습니다.",
        });
      }
      if (inquiry.riskLevel === "UNKNOWN" || inquiry.priority === "UNKNOWN") {
        throw new ApiClientError({
          kind: "PARSE_ERROR",
          message: "Mock 상세 정보를 API 계약 값으로 바꿀 수 없습니다.",
        });
      }
      const dto: ConsultantInquiryDetailDto = {
        inquiry: {
          inquiry_id: inquiry.inquiryId,
          inquiry_code: inquiry.inquiryCode,
          status: toStatus(inquiry.status),
          state_version: inquiry.stateVersion,
          risk_level: inquiry.riskLevel.toLowerCase() as "general" | "caution" | "danger",
          priority: inquiry.priority,
          received_at: inquiry.createdAt,
          updated_at: inquiry.updatedAt,
        },
        customer: {
          is_synthetic: true,
          display_name: inquiry.customerDisplayName,
          phone: inquiry.customerPhone,
          phone_masked: maskCustomerPhone(inquiry.customerPhone),
        },
        product_and_care: {
          product_model: inquiry.manualModel,
          product_model_name: inquiry.manualModel,
          subscription_status: "ACTIVE",
          management_type: inquiry.managementType,
          recent_care_date: inquiry.lastCareDate.slice(0, 10),
        },
        symptom_and_questionnaire: {
          symptom_summary: inquiry.customerMessage,
          answers: [],
        },
        guidance_and_actions: {
          usage_guidance_status: inquiry.usageStatus,
          usage_guidance_display_label:
            USAGE_GUIDANCE_DISPLAY_LABELS[inquiry.usageStatus],
          usage_guidance_message: inquiry.usageMessage,
          restricted_functions: inquiry.restrictedFunctions,
        },
        consultation: null,
        visit: null,
        state_history: [],
        workflow: {
          status: toStatus(inquiry.status),
          state_version: inquiry.stateVersion,
          allowed_actions: inquiry.allowedActions.map(toAllowedActionDto),
        },
        section_errors: [],
      };
      return {
        data: mapConsultantInquiryDetail(dto),
        correlationId: "mock-consultant-workspace",
      };
    },
  };
}

export function createMockConsultantInquiryListViewModel(
  query: ConsultantInquiryListQuery = {},
  dataset: MockDataset = appEnv.mockDataset,
): ConsultantInquiryListViewModel {
  const mockInquiries = getMockInquiries(dataset);
  const filtered = mockInquiries.filter((item) =>
    matchesMockQuery(item, query),
  );
  const page = query.page ?? 1;
  const size = query.size ?? 20;
  const start = (page - 1) * size;
  const statusCounts = mockInquiries.reduce<
    Partial<Record<ConsultantInquiryStatusDto, number>>
  >((counts, item) => {
    const status = toStatus(item.status);
    counts[status] = (counts[status] ?? 0) + 1;
    return counts;
  }, {});
  const dto: ConsultantInquiryListDataDto = {
    items: filtered.slice(start, start + size).map(toMockListItem),
    page_info: { page, size, total: filtered.length },
    status_counts: statusCounts,
  };
  return mapConsultantInquiryList(dto);
}

export function createMockUnassignedConsultationQueueViewModel(
  query: UnassignedConsultationQueueQuery = {},
  dataset: MockDataset = appEnv.mockDataset,
): UnassignedConsultationQueueViewModel {
  const mockInquiries = getMockUnassignedInquiries(dataset);
  const filtered = mockInquiries.filter((item) =>
    matchesMockQuery(item, query),
  );
  const page = query.page ?? 1;
  const size = query.size ?? 20;
  const start = (page - 1) * size;
  const dto: UnassignedConsultationQueueDataDto = {
    items: filtered.slice(start, start + size).map(toMockUnassignedQueueItem),
    page_info: { page, size, total: filtered.length },
  };
  return mapUnassignedConsultationQueue(dto);
}

export function createConsultantWorkspaceDataRepository(
  useMockApi: boolean,
): ConsultantWorkspaceDataRepository {
  return useMockApi
    ? createMockConsultantWorkspaceDataRepository()
    : createRemoteConsultantWorkspaceDataRepository();
}

export const consultantWorkspaceDataRepository =
  createConsultantWorkspaceDataRepository(appEnv.useMockApi);
