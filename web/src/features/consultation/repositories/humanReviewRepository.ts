import type { ApiResponse } from "../../../common/api/apiResponse";
import {
  requestApi,
  type ApiRequestOptions,
} from "../../../common/api/httpClient";
import type { RequestContext } from "../../../common/api/requestContext";
import type {
  HumanReviewDecisionRequestDto,
  HumanReviewDto,
  HumanReviewListDataDto,
} from "../api/humanReviewRemoteTypes";

export type HumanReviewRequester = <TData>(
  path: string,
  options?: ApiRequestOptions,
) => Promise<ApiResponse<TData>>;

export interface HumanReviewRepository {
  list(): Promise<ApiResponse<HumanReviewListDataDto>>;
  decide(
    reviewId: string,
    body: HumanReviewDecisionRequestDto,
    requestContext: RequestContext,
  ): Promise<ApiResponse<HumanReviewDto>>;
}

export function createRemoteHumanReviewRepository(
  requester: HumanReviewRequester = requestApi,
): HumanReviewRepository {
  return {
    list: () => requester<HumanReviewListDataDto>("/inquiries/human-reviews"),
    decide: (reviewId, body, requestContext) =>
      requester<HumanReviewDto>(
        `/inquiries/human-reviews/${encodeURIComponent(reviewId)}/decision`,
        { method: "POST", body, requestContext },
      ),
  };
}

export const humanReviewRepository = createRemoteHumanReviewRepository();
