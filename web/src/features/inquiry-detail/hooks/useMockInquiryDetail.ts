import { useMemo } from "react";

import { mapInquiryDetailToViewModel } from "../model/inquiryDetailMapper";
import { MOCK_INQUIRY_DETAILS } from "../model/inquiryDetailMock";
import type { InquiryDetailQueryResult } from "../model/inquiryDetailTypes";

function getMockInquiryDetailResult(
  inquiryId?: string,
): InquiryDetailQueryResult {
  if (inquiryId === "DEMO-INQ-LOADING") {
    return { status: "loading" };
  }

  if (inquiryId === "DEMO-INQ-ERROR") {
    return { status: "error" };
  }

  if (inquiryId === "DEMO-INQ-FORBIDDEN") {
    return { status: "forbidden" };
  }

  const inquiry = inquiryId
    ? MOCK_INQUIRY_DETAILS[inquiryId]
    : undefined;

  return inquiry
    ? {
        status: "success",
        data: mapInquiryDetailToViewModel(inquiry),
      }
    : { status: "notFound" };
}

export default function useMockInquiryDetail(inquiryId?: string) {
  return useMemo(() => getMockInquiryDetailResult(inquiryId), [inquiryId]);
}
