import type { InquiryDetail } from "./inquiryDetailTypes";

// Mock: 문의 상세 API 계약이 확정되기 전 화면과 상태별 동작 검증용 데이터입니다.
export const MOCK_INQUIRY_DETAILS: Record<string, InquiryDetail> = {
  "DEMO-INQ-001": {
    inquiryId: "DEMO-INQ-001",
    customerDisplayName: "김*수",
    maskedPhone: "010-****-1234",
    productModel: "WPUJAC104DWH",
    subscriptionType: "정기 구독",
    careType: "방문 관리",
    symptomSummary: "출수량이 이전보다 줄어들었어요.",
    customerMessage:
      "며칠 전부터 정수기에서 나오는 물의 양이 이전보다 적어진 것 같습니다.",
    questionnaireAnswer:
      "냉수와 정수 모두 출수량이 줄었으며, 제품 외부 누수는 확인되지 않았습니다.",
    currentStateLabel: "상담 필요",
    currentAssigneeLabel: "상담사",
    riskLevel: "general",
    priorityLabel: "보통",
    priorityVariant: "default",
    aiSummary:
      "출수량 저하 문의입니다. 필터 사용 기간과 출수구 막힘 여부를 우선 확인하고, 해결되지 않을 경우 방문 점검 전환을 검토해 주세요.",
    responseDraft:
      "안녕하세요, 고객님. 출수량 감소로 불편을 드려 죄송합니다. 먼저 출수구 주변에 이물질이 있는지 확인해 주세요. 동일 증상이 계속되면 방문 점검을 도와드리겠습니다.",
    stateVersion: 3,
    allowedActions: [
      "SAVE_RESPONSE_DRAFT",
      "SEND_RESPONSE",
      "REQUEST_VISIT",
    ],
    evidence: [
      {
        documentTitle: "JAC104D 사용 설명서",
        revision: "Rev. 1.0",
        page: 24,
        summary:
          "출수량이 감소한 경우 필터 사용 기간과 출수구 상태를 확인하도록 안내합니다.",
        verificationStatus: "VERIFIED",
      },
    ],
    statusHistory: [
      {
        status: "문의 접수",
        event: "고객 문의 등록",
        actor: "고객",
        occurredAt: "2026-07-27 09:20",
      },
      {
        status: "AI 안내 완료",
        event: "AI 증상 분석 및 상담 연결",
        actor: "시스템",
        occurredAt: "2026-07-27 09:21",
      },
      {
        status: "상담 필요",
        event: "상담사 확인 대기",
        actor: "시스템",
        occurredAt: "2026-07-27 09:22",
      },
    ],
  },
  "DEMO-INQ-002": {
    inquiryId: "DEMO-INQ-002",
    customerDisplayName: "이*영",
    maskedPhone: "010-****-5678",
    productModel: "WPUJAC104DWH",
    subscriptionType: "정기 구독",
    careType: "방문 관리",
    symptomSummary: "제품 하단에서 물이 새는 것 같아요.",
    customerMessage:
      "제품 아래쪽 바닥에 물이 고여 있습니다. 현재는 사용을 멈춘 상태입니다.",
    questionnaireAnswer:
      "제품 하단에서 물이 확인되었으며, 전원 플러그 주변에는 물이 닿지 않았습니다.",
    currentStateLabel: "상담 필요",
    currentAssigneeLabel: "상담사",
    riskLevel: "danger",
    priorityLabel: "긴급",
    priorityVariant: "urgent",
    aiSummary:
      "누수 의심 문의입니다. 고객에게 제품 사용 중지를 유지하도록 안내하고, 임의 분해나 부품 교체를 안내하지 마세요. 상담사 확인 후 방문 점검 전환이 필요합니다.",
    responseDraft:
      "안녕하세요, 고객님. 안전을 위해 제품 사용을 중지한 상태를 유지해 주세요. 제품을 직접 분해하거나 부품을 교체하지 마시고, 방문 점검을 접수해 드리겠습니다.",
    stateVersion: 4,
    allowedActions: ["SAVE_RESPONSE_DRAFT", "REQUEST_VISIT"],
    evidence: [
      {
        documentTitle: "JAC104D 안전 사용 안내",
        revision: "Rev. 1.0",
        page: 6,
        summary:
          "누수 의심 시 제품 사용을 중지하고 고객센터 또는 서비스 담당자에게 문의하도록 안내합니다.",
        verificationStatus: "VERIFIED",
      },
    ],
    statusHistory: [
      {
        status: "문의 접수",
        event: "고객 누수 문의 등록",
        actor: "고객",
        occurredAt: "2026-07-27 09:45",
      },
      {
        status: "위험 감지",
        event: "누수 위험 시나리오 감지",
        actor: "시스템",
        occurredAt: "2026-07-27 09:46",
      },
      {
        status: "상담 필요",
        event: "긴급 상담사 연결 요청",
        actor: "시스템",
        occurredAt: "2026-07-27 09:46",
      },
    ],
  },
  "DEMO-INQ-003": {
    inquiryId: "DEMO-INQ-003",
    customerDisplayName: "박*진",
    maskedPhone: "010-****-9012",
    productModel: "WPUJAC104DWH",
    subscriptionType: "정기 구독",
    careType: "방문 관리",
    symptomSummary: "이전에 처리했지만 같은 증상이 다시 발생했어요.",
    customerMessage:
      "지난 상담 이후 잠시 괜찮았지만 같은 증상이 다시 발생했습니다.",
    questionnaireAnswer:
      "이전 안내에 따라 제품을 재시작했으나 증상이 다시 나타났습니다.",
    currentStateLabel: "문의 재개",
    currentAssigneeLabel: "상담사",
    riskLevel: "caution",
    priorityLabel: "높음",
    priorityVariant: "high",
    aiSummary:
      "동일 증상이 재발한 문의입니다. 이전 상담 기록과 고객 조치 결과를 확인하고, 반복 안내보다 방문 점검 필요 여부를 우선 검토해 주세요.",
    responseDraft:
      "안녕하세요, 고객님. 같은 증상이 다시 발생해 불편을 드려 죄송합니다. 이전 상담 이력을 확인했으며, 정확한 점검을 위해 방문 서비스 전환을 안내드리겠습니다.",
    stateVersion: 5,
    allowedActions: [
      "SAVE_RESPONSE_DRAFT",
      "SEND_RESPONSE",
      "REQUEST_VISIT",
    ],
    evidence: [],
    statusHistory: [
      {
        status: "상담 완료",
        event: "초기 상담 안내 완료",
        actor: "상담사",
        occurredAt: "2026-07-25 14:10",
      },
      {
        status: "문의 재개",
        event: "고객 미해결 피드백 제출",
        actor: "고객",
        occurredAt: "2026-07-27 10:10",
      },
    ],
  },
};
