import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiClientError } from "../../../common/api/apiError";
import type { ConsultantInquiryListQuery } from "../api/consultantWorkspaceRemoteTypes";
import type {
  ConsultantInquiryDetailViewModel,
  ConsultantInquiryListViewModel,
} from "../model/consultantWorkspaceRemoteMapper";
import {
  consultantWorkspaceDataRepository,
  type ConsultantWorkspaceDataRepository,
} from "../repositories/consultantWorkspaceDataRepository";

export type ConsultantQueryStatus = "idle" | "loading" | "success" | "error";

interface QueryState<TData> {
  correlationId: string | null;
  data: TData | null;
  error: unknown | null;
  status: ConsultantQueryStatus;
}

interface StoredQueryState<TData> extends QueryState<TData> {
  requestKey: string;
}

export interface ConsultantQueryResult<TData> extends QueryState<TData> {
  isConflict: boolean;
  isForbidden: boolean;
  isNotFound: boolean;
  retry: () => void;
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiClientError && error.status === status;
}

function getErrorCorrelationId(error: unknown): string | null {
  return error instanceof ApiClientError ? (error.correlationId ?? null) : null;
}

export function useConsultantInquiryListQuery(
  query: ConsultantInquiryListQuery,
  repository: ConsultantWorkspaceDataRepository = consultantWorkspaceDataRepository,
): ConsultantQueryResult<ConsultantInquiryListViewModel> {
  const queryKey = JSON.stringify(query);
  const stableQuery = useMemo(
    () => JSON.parse(queryKey) as ConsultantInquiryListQuery,
    [queryKey],
  );
  const [retryCount, setRetryCount] = useState(0);
  const requestKey = `${queryKey}:${retryCount}`;
  const [state, setState] = useState<
    StoredQueryState<ConsultantInquiryListViewModel>
  >({
    correlationId: null,
    data: null,
    error: null,
    requestKey: "",
    status: "loading",
  });

  useEffect(() => {
    let active = true;
    repository.listInquiries(stableQuery).then(
      (result) => {
        if (active) {
          setState({
            correlationId: result.correlationId,
            data: result.data,
            error: null,
            requestKey,
            status: "success",
          });
        }
      },
      (error: unknown) => {
        if (active) {
          setState({
            correlationId: getErrorCorrelationId(error),
            data: null,
            error,
            requestKey,
            status: "error",
          });
        }
      },
    );
    return () => {
      active = false;
    };
  }, [repository, requestKey, stableQuery]);

  const retry = useCallback(() => setRetryCount((count) => count + 1), []);
  const currentState: QueryState<ConsultantInquiryListViewModel> =
    state.requestKey === requestKey
      ? state
      : { correlationId: null, data: null, error: null, status: "loading" };
  return {
    ...currentState,
    isConflict:
      hasStatus(currentState.error, 409) ||
      (currentState.error instanceof ApiClientError &&
        currentState.error.kind === "CONFLICT"),
    isForbidden: hasStatus(currentState.error, 403),
    isNotFound: hasStatus(currentState.error, 404),
    retry,
  };
}

export function useConsultantInquiryDetailQuery(
  inquiryId: string | null,
  repository: ConsultantWorkspaceDataRepository = consultantWorkspaceDataRepository,
): ConsultantQueryResult<ConsultantInquiryDetailViewModel> {
  const [retryCount, setRetryCount] = useState(0);
  const requestKey = `${inquiryId ?? "idle"}:${retryCount}`;
  const [state, setState] = useState<
    StoredQueryState<ConsultantInquiryDetailViewModel>
  >({
    correlationId: null,
    data: null,
    error: null,
    requestKey: "",
    status: "idle",
  });

  useEffect(() => {
    let active = true;
    if (!inquiryId) {
      return () => {
        active = false;
      };
    }
    repository.getInquiryDetail(inquiryId).then(
      (result) => {
        if (active) {
          setState({
            correlationId: result.correlationId,
            data: result.data,
            error: null,
            requestKey,
            status: "success",
          });
        }
      },
      (error: unknown) => {
        if (active) {
          setState({
            correlationId: getErrorCorrelationId(error),
            data: null,
            error,
            requestKey,
            status: "error",
          });
        }
      },
    );
    return () => {
      active = false;
    };
  }, [inquiryId, repository, requestKey]);

  const retry = useCallback(() => setRetryCount((count) => count + 1), []);
  const previousDataForSameInquiry =
    state.data !== null && state.data.inquiryId === inquiryId;
  const currentState: QueryState<ConsultantInquiryDetailViewModel> = !inquiryId
    ? { correlationId: null, data: null, error: null, status: "idle" }
    : state.requestKey === requestKey
      ? state
      : previousDataForSameInquiry
        ? {
            correlationId: state.correlationId,
            data: state.data,
            error: null,
            status: "success",
          }
        : {
            correlationId: null,
            data: null,
            error: null,
            status: "loading",
          };
  return {
    ...currentState,
    isConflict:
      hasStatus(currentState.error, 409) ||
      (currentState.error instanceof ApiClientError &&
        currentState.error.kind === "CONFLICT"),
    isForbidden: hasStatus(currentState.error, 403),
    isNotFound: hasStatus(currentState.error, 404),
    retry,
  };
}
