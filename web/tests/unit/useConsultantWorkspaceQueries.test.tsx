import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../src/common/api/apiError";
import {
  useConsultantInquiryDetailQuery,
  useConsultantInquiryListQuery,
  useUnassignedConsultationQueueQuery,
} from "../../src/features/consultation/hooks/useConsultantWorkspaceQueries";
import type {
  ConsultantInquiryDetailViewModel,
  ConsultantInquiryListViewModel,
  UnassignedConsultationQueueViewModel,
} from "../../src/features/consultation/model/consultantWorkspaceRemoteMapper";
import type { ConsultantWorkspaceDataRepository } from "../../src/features/consultation/repositories/consultantWorkspaceDataRepository";

const EMPTY_LIST: ConsultantInquiryListViewModel = {
  items: [],
  pageInfo: { page: 1, size: 10, total: 0 },
  statusCounts: {},
};

const UNASSIGNED_QUEUE: UnassignedConsultationQueueViewModel = {
  items: [],
  pageInfo: { page: 1, size: 3, total: 0 },
};

const DETAIL: ConsultantInquiryDetailViewModel = {
  inquiryId: "b7df3cd0-c9d6-42bd-b93e-a70ee24c6f21",
  inquiryCode: "INQ-001",
  status: "CONSULTATION_REQUIRED",
  stateVersion: 3,
  riskLevel: "danger",
  priority: "URGENT",
  receivedAt: "2026-08-10T09:00:00+09:00",
  updatedAt: "2026-08-10T09:10:00+09:00",
  customer: {
    isSynthetic: true,
    displayName: "합성 고객 001",
    phoneMasked: "010-****-0001",
    phoneDisplay: "010-****-0001",
  },
  productAndCare: null,
  symptomAndQuestionnaire: {
    symptomSummary: "누수",
    answers: [],
  },
  guidanceAndActions: {
    usageGuidanceStatus: "PENDING_CONSULTATION",
    usageGuidanceDisplayLabel: "상담 확인 필요",
    usageGuidanceMessage: null,
    restrictedFunctions: [],
  },
  consultation: null,
  visit: null,
  stateHistory: [],
  workflow: {
    status: "CONSULTATION_REQUIRED",
    stateVersion: 3,
    allowedActions: [],
  },
  sectionErrors: [],
};

function createRepository(
  overrides: Partial<ConsultantWorkspaceDataRepository> = {},
): ConsultantWorkspaceDataRepository {
  return {
    dataSource: "REMOTE",
    listInquiries: vi.fn(async () => ({
      data: EMPTY_LIST,
      correlationId: "corr-list",
    })),
    listUnassignedConsultations: vi.fn(async () => ({
      data: UNASSIGNED_QUEUE,
      correlationId: "corr-unassigned",
    })),
    getInquiryDetail: vi.fn(async () => ({
      data: DETAIL,
      correlationId: "corr-detail",
    })),
    ...overrides,
  };
}

describe("상담사 화면 비동기 Query 상태", () => {
  it("목록 조회의 loading과 success를 화면에 전달한다", async () => {
    let resolveRequest: ((value: { data: ConsultantInquiryListViewModel; correlationId: string }) => void) | undefined;
    const repository = createRepository({
      listInquiries: vi.fn(
        () =>
          new Promise((resolve) => {
            resolveRequest = resolve;
          }),
      ),
    });

    const { result } = renderHook(() =>
      useConsultantInquiryListQuery({ page: 1, size: 10 }, repository),
    );

    expect(result.current.status).toBe("loading");
    act(() => {
      resolveRequest?.({ data: EMPTY_LIST, correlationId: "corr-list" });
    });
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.data).toEqual(EMPTY_LIST);
    expect(result.current.correlationId).toBe("corr-list");
  });

  it("목록 오류 뒤 재시도하면 같은 Query를 다시 호출한다", async () => {
    const listInquiries = vi
      .fn()
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce({ data: EMPTY_LIST, correlationId: "corr-retry" });
    const repository = createRepository({ listInquiries });
    const query = { q: "누수", page: 1, size: 10 };

    const { result } = renderHook(() =>
      useConsultantInquiryListQuery(query, repository),
    );

    await waitFor(() => expect(result.current.status).toBe("error"));
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(listInquiries).toHaveBeenCalledTimes(2);
    expect(listInquiries).toHaveBeenLastCalledWith(query);
  });

  it("미배정 상담 목록을 별도 Query로 조회하고 오류 뒤 다시 불러온다", async () => {
    const listUnassignedConsultations = vi
      .fn()
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce({
        data: UNASSIGNED_QUEUE,
        correlationId: "corr-unassigned-retry",
      });
    const repository = createRepository({ listUnassignedConsultations });
    const query = { sort: "WAITING_DESC" as const, page: 1, size: 3 };

    const { result } = renderHook(() =>
      useUnassignedConsultationQueueQuery(query, repository),
    );

    await waitFor(() => expect(result.current.status).toBe("error"));
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.status).toBe("success"));

    expect(result.current.data).toEqual(UNASSIGNED_QUEUE);
    expect(result.current.correlationId).toBe("corr-unassigned-retry");
    expect(listUnassignedConsultations).toHaveBeenCalledTimes(2);
    expect(listUnassignedConsultations).toHaveBeenLastCalledWith(query);
  });

  it("상세 403 오류를 권한 오류로 구분한다", async () => {
    const repository = createRepository({
      getInquiryDetail: vi.fn(async () => {
        throw new ApiClientError({
          correlationId: "corr-forbidden",
          kind: "FORBIDDEN",
          status: 403,
          message: "forbidden",
        });
      }),
    });

    const { result } = renderHook(() =>
      useConsultantInquiryDetailQuery(DETAIL.inquiryId, repository),
    );

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.isForbidden).toBe(true);
    expect(result.current.correlationId).toBe("corr-forbidden");
  });

  it("상세 404는 배정 여부를 구분하지 않는 찾을 수 없음 상태로 전달한다", async () => {
    const repository = createRepository({
      getInquiryDetail: vi.fn(async () => {
        throw new ApiClientError({
          kind: "NOT_FOUND",
          status: 404,
          message: "not found",
        });
      }),
    });

    const { result } = renderHook(() =>
      useConsultantInquiryDetailQuery(DETAIL.inquiryId, repository),
    );

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.isNotFound).toBe(true);
    expect(result.current.isForbidden).toBe(false);
  });

  it("같은 문의 재조회 중에는 기존 상세를 유지해 작성 Form을 언마운트하지 않는다", async () => {
    let resolveRefresh:
      | ((value: {
          data: ConsultantInquiryDetailViewModel;
          correlationId: string;
        }) => void)
      | undefined;
    const refreshedDetail = {
      ...DETAIL,
      status: "CONSULTATION_IN_PROGRESS" as const,
      stateVersion: 4,
      workflow: {
        ...DETAIL.workflow,
        status: "CONSULTATION_IN_PROGRESS" as const,
        stateVersion: 4,
      },
    };
    const getInquiryDetail = vi
      .fn()
      .mockResolvedValueOnce({ data: DETAIL, correlationId: "corr-detail" })
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveRefresh = resolve;
        }),
      );
    const repository = createRepository({ getInquiryDetail });

    const { result } = renderHook(() =>
      useConsultantInquiryDetailQuery(DETAIL.inquiryId, repository),
    );

    await waitFor(() => expect(result.current.status).toBe("success"));
    act(() => result.current.retry());

    expect(result.current.status).toBe("success");
    expect(result.current.data).toEqual(DETAIL);

    act(() => {
      resolveRefresh?.({
        data: refreshedDetail,
        correlationId: "corr-refresh",
      });
    });
    await waitFor(() => expect(result.current.data?.stateVersion).toBe(4));
    expect(getInquiryDetail).toHaveBeenCalledTimes(2);
    expect(result.current.correlationId).toBe("corr-refresh");
  });

  it("문의 ID가 없으면 상세 API를 호출하지 않는다", () => {
    const repository = createRepository();

    const { result } = renderHook(() =>
      useConsultantInquiryDetailQuery(null, repository),
    );

    expect(result.current.status).toBe("idle");
    expect(repository.getInquiryDetail).not.toHaveBeenCalled();
  });
});
