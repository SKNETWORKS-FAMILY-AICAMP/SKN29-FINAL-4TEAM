import { useSearchParams } from "react-router-dom";

import {
  PRIORITY_FILTER_VALUES,
  RISK_FILTER_VALUES,
  SORT_VALUES,
  STATUS_FILTER_VALUES,
} from "../model/inquiryQueueConstants";
import type { InquiryQueueFilters } from "../model/inquiryQueueTypes";

function getValidatedParam<T extends string>(
  searchParams: URLSearchParams,
  key: string,
  allowedValues: readonly T[],
  fallback: T,
): T {
  const value = searchParams.get(key);

  return value && allowedValues.includes(value as T)
    ? (value as T)
    : fallback;
}

function getPageParam(searchParams: URLSearchParams): number {
  const value = Number(searchParams.get("page") ?? "1");

  return Number.isInteger(value) && value > 0 ? value : 1;
}

export default function useInquiryQueueFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters: InquiryQueueFilters = {
    page: getPageParam(searchParams),
    priority: getValidatedParam(
      searchParams,
      "priority",
      PRIORITY_FILTER_VALUES,
      "ALL",
    ),
    risk: getValidatedParam(
      searchParams,
      "risk",
      RISK_FILTER_VALUES,
      "ALL",
    ),
    searchKeyword: searchParams.get("q") ?? "",
    sort: getValidatedParam(
      searchParams,
      "sort",
      SORT_VALUES,
      "RECEIVED_DESC",
    ),
    status: getValidatedParam(
      searchParams,
      "status",
      STATUS_FILTER_VALUES,
      "ALL",
    ),
  };

  const updateSearchParam = (
    key: string,
    value: string,
    defaultValue: string,
  ) => {
    const nextParams = new URLSearchParams(searchParams);

    if (value === defaultValue || value.trim().length === 0) {
      nextParams.delete(key);
    } else {
      nextParams.set(key, value);
    }

    if (key !== "page") {
      nextParams.delete("page");
    }

    setSearchParams(nextParams, { replace: true });
  };

  return {
    filters,
    resetFilters: () =>
      setSearchParams(new URLSearchParams(), { replace: true }),
    setPage: (page: number) =>
      updateSearchParam("page", String(page), "1"),
    setPriority: (priority: string) =>
      updateSearchParam("priority", priority, "ALL"),
    setRisk: (risk: string) => updateSearchParam("risk", risk, "ALL"),
    setSearchKeyword: (searchKeyword: string) =>
      updateSearchParam("q", searchKeyword, ""),
    setSort: (sort: string) =>
      updateSearchParam("sort", sort, "RECEIVED_DESC"),
    setStatus: (status: string) =>
      updateSearchParam("status", status, "ALL"),
  };
}
