import { useMemo } from "react";

import { mapInquiryDetailToViewModel } from "../model/inquiryDetailMapper";
import {
  MOCK_INQUIRY_DETAIL_FAILURE_SCENARIOS,
  MOCK_INQUIRY_DETAILS,
} from "../model/inquiryDetailMock";
import type {
  InquiryDetailQueryResult,
  InquiryDetailSectionStates,
} from "../model/inquiryDetailTypes";

const READY_SECTIONS: InquiryDetailSectionStates = {
  aiSummary: "ready",
  evidence: "ready",
  statusHistory: "ready",
};

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

  const failureScenario = inquiryId
    ? MOCK_INQUIRY_DETAIL_FAILURE_SCENARIOS[inquiryId]
    : undefined;
  const sourceInquiryId = failureScenario?.sourceInquiryId ?? inquiryId;
  const inquiry = sourceInquiryId
    ? MOCK_INQUIRY_DETAILS[sourceInquiryId]
    : undefined;

  return inquiry
    ? {
        status: "success",
        data: {
          ...mapInquiryDetailToViewModel(inquiry),
          inquiryId: inquiryId ?? inquiry.inquiryId,
        },
        sections: failureScenario?.sections ?? READY_SECTIONS,
      }
    : { status: "notFound" };
}

export default function useMockInquiryDetail(inquiryId?: string) {
  return useMemo(() => getMockInquiryDetailResult(inquiryId), [inquiryId]);
}
