import type { InquiryListItem } from "./inquiryQueueTypes";

// Mock: 실제 상담사 문의 목록 API로 교체하기 전 화면 검증용 합성 데이터입니다.
export const MOCK_INQUIRIES: InquiryListItem[] = [
  {
    inquiryId: "DEMO-INQ-001",
    customerDisplayName: "김*수",
    productModel: "WPUJAC104DWH",
    symptomSummary: "출수량이 이전보다 줄어들었어요.",
    currentState: "CONSULTATION_REQUIRED",
    riskLevel: "general",
    priorityLabel: "보통",
    priorityVariant: "default",
    receivedAt: "2026-07-27T09:20:00+09:00",
  },
  {
    inquiryId: "DEMO-INQ-002",
    customerDisplayName: "이*영",
    productModel: "WPUJAC104DWH",
    symptomSummary: "제품 하단에서 물이 새는 것 같아요.",
    currentState: "CONSULTATION_REQUIRED",
    riskLevel: "danger",
    priorityLabel: "긴급",
    priorityVariant: "urgent",
    receivedAt: "2026-07-27T09:45:00+09:00",
  },
  {
    inquiryId: "DEMO-INQ-003",
    customerDisplayName: "박*진",
    productModel: "WPUJAC104DWH",
    symptomSummary: "이전에 처리했지만 같은 증상이 다시 발생했어요.",
    currentState: "REOPENED",
    riskLevel: "caution",
    priorityLabel: "높음",
    priorityVariant: "high",
    receivedAt: "2026-07-27T10:10:00+09:00",
  },
];
