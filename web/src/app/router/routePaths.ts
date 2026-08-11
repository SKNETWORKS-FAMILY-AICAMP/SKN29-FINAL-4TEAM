export const ROUTE_PATHS = {
  home: "/",
  login: "/login",
  forbidden: "/forbidden",
  error: "/error",
  adminDashboard: "/admin",
  adminInsights: "/admin/insights",
  consultantInquiryList: "/consultant/inquiries",
  consultantPhoneInquiryCreate: "/consultant/phone-inquiries/new",
  consultantInquiryDetail: "/consultant/inquiries/:inquiryId",
  consultantVisitTransition:
    "/consultant/inquiries/:inquiryId/visit-transition",
} as const;

export function createInquiryDetailPath(inquiryId: InquiryId): string {
  return `/consultant/inquiries/${encodeURIComponent(inquiryId)}`;
}

export function createVisitTransitionPath(inquiryId: InquiryId): string {
  return `/consultant/inquiries/${encodeURIComponent(
    inquiryId,
  )}/visit-transition`;
}

export function getSafeInquiryListReturnPath(value: unknown): string {
  if (
    typeof value === "string" &&
    (value === ROUTE_PATHS.consultantInquiryList ||
      value.startsWith(`${ROUTE_PATHS.consultantInquiryList}?`))
  ) {
    return value;
  }

  return ROUTE_PATHS.consultantInquiryList;
}
import type { InquiryId } from "../../entities/inquiry/inquiryIdentifiers";
