import { useMemo } from "react";

import type {
  ConsultantInquiryListQuery,
  ConsultantInquiryStatusDto,
} from "../api/consultantWorkspaceRemoteTypes";
import type { CounselorWorkBucket } from "../model/consultantWorkspaceTypes";
import {
  consultantWorkspaceDataRepository,
  createMockConsultantInquiryListViewModel,
} from "../repositories/consultantWorkspaceDataRepository";
import { useConsultantInquiryListQuery } from "./useConsultantWorkspaceQueries";

const SIDEBAR_BUCKET_STATUSES: Record<
  CounselorWorkBucket,
  readonly ConsultantInquiryStatusDto[]
> = {
  NEW: ["CONSULTATION_REQUIRED", "REOPENED"],
  IN_PROGRESS: [
    "DRAFT",
    "QUESTIONNAIRE_IN_PROGRESS",
    "AI_GUIDANCE",
    "CONSULTATION_IN_PROGRESS",
    "VISIT_REVIEW_PENDING",
    "VISIT_SCHEDULING",
    "VISIT_SCHEDULED",
    "COMPLETION_PENDING",
    "REVISIT_REQUIRED",
  ],
  COMPLETED: ["RESOLVED", "CANCELLED"],
};

const SIDEBAR_QUERY: ConsultantInquiryListQuery = {
  status: [
    ...SIDEBAR_BUCKET_STATUSES.NEW,
    ...SIDEBAR_BUCKET_STATUSES.IN_PROGRESS,
    ...SIDEBAR_BUCKET_STATUSES.COMPLETED,
  ],
  page: 1,
  size: 100,
};

/** Directory filters must never change the consultant's overall inquiry totals. */
export function useConsultantSidebarSummary() {
  const query = useConsultantInquiryListQuery(SIDEBAR_QUERY);
  const data = useMemo(
    () =>
      consultantWorkspaceDataRepository.dataSource === "MOCK"
        ? createMockConsultantInquiryListViewModel(SIDEBAR_QUERY)
        : query.data,
    [query.data],
  );
  const bucketCounts = useMemo<
    Readonly<Record<CounselorWorkBucket, number>> | undefined
  >(
    () =>
      data
        ? (Object.fromEntries(
            Object.entries(SIDEBAR_BUCKET_STATUSES).map(([bucket, statuses]) => [
              bucket,
              statuses.reduce(
                (total, status) => total + (data.statusCounts[status] ?? 0),
                0,
              ),
            ]),
          ) as Record<CounselorWorkBucket, number>)
        : undefined,
    [data],
  );

  return { bucketCounts, totalCount: data?.pageInfo.total };
}
