import { useMemo } from "react";

import { INQUIRY_QUEUE_PAGE_SIZE } from "../model/inquiryQueueConstants";
import { getInquiryQueuePage } from "../model/inquiryQueueModel";
import { MOCK_INQUIRIES } from "../model/inquiryQueueMock";
import type { InquiryQueueFilters } from "../model/inquiryQueueTypes";

export default function useMockInquiryQueue(filters: InquiryQueueFilters) {
  const { page, priority, risk, searchKeyword, sort, status } = filters;

  return useMemo(
    () =>
      getInquiryQueuePage(
        MOCK_INQUIRIES,
        { page, priority, risk, searchKeyword, sort, status },
        INQUIRY_QUEUE_PAGE_SIZE,
      ),
    [page, priority, risk, searchKeyword, sort, status],
  );
}
