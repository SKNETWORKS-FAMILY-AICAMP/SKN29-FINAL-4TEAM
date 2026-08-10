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
  data: TData | null;
  error: unknown | null;
  status: ConsultantQueryStatus;
}

interface StoredQueryState<TData> extends QueryState<TData> {
  requestKey: string;
}

export interface ConsultantQueryResult<TData> extends QueryState<TData> {
  isForbidden: boolean;
  isNotFound: boolean;
  retry: () => void;
}

function hasStatus(error: unknown, status: number): boolean {
  return error instanceof ApiClientError && error.status === status;
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
  >({ data: null, error: null, requestKey: "", status: "loading" });

  useEffect(() => {
    let active = true;
    repository.listInquiries(stableQuery).then(
      (result) => {
        if (active) {
          setState({
            data: result.data,
            error: null,
            requestKey,
            status: "success",
          });
        }
      },
      (error: unknown) => {
        if (active) {
          setState({ data: null, error, requestKey, status: "error" });
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
      : { data: null, error: null, status: "loading" };
  return {
    ...currentState,
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
  >({ data: null, error: null, requestKey: "", status: "idle" });

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
            data: result.data,
            error: null,
            requestKey,
            status: "success",
          });
        }
      },
      (error: unknown) => {
        if (active) {
          setState({ data: null, error, requestKey, status: "error" });
        }
      },
    );
    return () => {
      active = false;
    };
  }, [inquiryId, repository, requestKey]);

  const retry = useCallback(() => setRetryCount((count) => count + 1), []);
  const currentState: QueryState<ConsultantInquiryDetailViewModel> = !inquiryId
    ? { data: null, error: null, status: "idle" }
    : state.requestKey === requestKey
      ? state
      : { data: null, error: null, status: "loading" };
  return {
    ...currentState,
    isForbidden: hasStatus(currentState.error, 403),
    isNotFound: hasStatus(currentState.error, 404),
    retry,
  };
}
