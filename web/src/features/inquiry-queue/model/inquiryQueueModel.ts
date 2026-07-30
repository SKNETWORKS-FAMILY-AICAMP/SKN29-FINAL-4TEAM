import type {
  InquiryListItem,
  InquiryQueueFilters,
  InquiryQueuePage,
} from "./inquiryQueueTypes";
import { formatContractDateTimeShort } from "../../../common/date-time/contractDateTime";

export function formatInquiryReceivedAt(value: string): string {
  return formatContractDateTimeShort(value) ?? "-";
}

function getReceivedTimestamp(value: string): number {
  const timestamp = Date.parse(value);

  return Number.isNaN(timestamp) ? 0 : timestamp;
}

export function getInquiryQueuePage(
  inquiries: InquiryListItem[],
  filters: InquiryQueueFilters,
  pageSize: number,
): InquiryQueuePage {
  const keyword = filters.searchKeyword.trim().toLowerCase();

  const filteredInquiries = inquiries
    .filter((inquiry) => {
      const matchesKeyword =
        keyword.length === 0 ||
        inquiry.inquiryId.toLowerCase().includes(keyword) ||
        inquiry.customerDisplayName.toLowerCase().includes(keyword) ||
        inquiry.productModel.toLowerCase().includes(keyword) ||
        inquiry.symptomSummary.toLowerCase().includes(keyword);
      const matchesRisk =
        filters.risk === "ALL" || inquiry.riskLevel === filters.risk;
      const matchesStatus =
        filters.status === "ALL" ||
        inquiry.currentState === filters.status;
      const matchesPriority =
        filters.priority === "ALL" ||
        inquiry.priorityVariant === filters.priority;

      return (
        matchesKeyword &&
        matchesRisk &&
        matchesStatus &&
        matchesPriority
      );
    })
    .sort((left, right) => {
      const difference =
        getReceivedTimestamp(right.receivedAt) -
        getReceivedTimestamp(left.receivedAt);

      return filters.sort === "RECEIVED_DESC" ? difference : -difference;
    });

  const totalPages = Math.max(
    1,
    Math.ceil(filteredInquiries.length / pageSize),
  );
  const currentPage = Math.min(filters.page, totalPages);
  const hasActiveFilters =
    keyword.length > 0 ||
    filters.risk !== "ALL" ||
    filters.status !== "ALL" ||
    filters.priority !== "ALL";

  return {
    currentPage,
    hasActiveFilters,
    hasChangedConditions:
      hasActiveFilters || filters.sort !== "RECEIVED_DESC",
    items: filteredInquiries.slice(
      (currentPage - 1) * pageSize,
      currentPage * pageSize,
    ),
    totalItems: filteredInquiries.length,
    totalPages,
  };
}
