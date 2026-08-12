import { ApiClientError } from "../../../common/api/apiError";
import type { ApiResponse } from "../../../common/api/apiResponse";
import {
  requestApi,
  type ApiRequestOptions,
} from "../../../common/api/httpClient";
import type { RequestContext } from "../../../common/api/requestContext";
import type { AllowedActionDto } from "../api/consultantWorkspaceRemoteTypes";

export type PhoneInquirySymptomCode =
  | "NO_WATER"
  | "LOW_FLOW"
  | "LEAK"
  | "ODOR"
  | "TASTE"
  | "TEMPERATURE_ABNORMAL"
  | "NOISE"
  | "DISPLAY_ERROR"
  | "OTHER";

export type PhoneInquiryPriorityCode =
  | "LOW"
  | "NORMAL"
  | "HIGH"
  | "URGENT";

export interface CustomerSubscriptionCandidateDto {
  customer_id: string;
  customer_display_name: string;
  phone_masked: string;
  subscription_id: string;
  subscription_status: "ACTIVE";
  management_type_code: string;
  product_id: string;
  product_model_code: string;
  product_name: string;
}

export interface CustomerSubscriptionSearchResultDto {
  items: readonly CustomerSubscriptionCandidateDto[];
  returned_count: number;
}

export interface RegisterPhoneInquiryRequestDto {
  subscription_id: string;
  raw_text: string;
  representative_symptom_code: PhoneInquirySymptomCode;
  priority_code: PhoneInquiryPriorityCode;
}

export interface RegisterPhoneInquiryResultDto {
  inquiry_id: string;
  inquiry_code: string;
  status_code: "CONSULTATION_REQUIRED";
  state_version: 1;
  idempotent_replay: boolean;
  allowed_actions: readonly AllowedActionDto[];
}

export interface PhoneInquiryRepositoryResult<TData> {
  data: TData;
  correlationId: string;
}

export type PhoneInquiryApiRequester = <TData>(
  path: string,
  options: ApiRequestOptions,
) => Promise<ApiResponse<TData>>;

export interface PhoneInquiryRemoteRepository {
  searchCustomerSubscriptions(
    query: string,
    limit?: number,
  ): Promise<PhoneInquiryRepositoryResult<CustomerSubscriptionSearchResultDto>>;
  registerPhoneInquiry(
    body: RegisterPhoneInquiryRequestDto,
    requestContext: RequestContext,
  ): Promise<PhoneInquiryRepositoryResult<RegisterPhoneInquiryResultDto>>;
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

export function createPhoneInquiryRemoteRepository(
  requester: PhoneInquiryApiRequester = requestApi,
): PhoneInquiryRemoteRepository {
  return {
    async searchCustomerSubscriptions(query, limit = 10) {
      const response = await requester<CustomerSubscriptionSearchResultDto>(
        "/consultant/customer-subscriptions/search",
        {
          method: "POST",
          body: { query, limit },
        },
      );
      return {
        data: requireResponseData(response),
        correlationId: response.metadata.correlation_id,
      };
    },

    async registerPhoneInquiry(body, requestContext) {
      const response = await requester<RegisterPhoneInquiryResultDto>(
        "/consultant/phone-inquiries",
        {
          method: "POST",
          body,
          requestContext,
        },
      );
      return {
        data: requireResponseData(response),
        correlationId: response.metadata.correlation_id,
      };
    },
  };
}

export const phoneInquiryRemoteRepository =
  createPhoneInquiryRemoteRepository();
