import type {
  CounselorEvidence,
  CounselorInquiry,
} from "./consultantWorkspaceTypes";

const OFFICIAL_EVIDENCE: CounselorEvidence = {
  documentTitle: "SK매직 WPU-JAC104D/JCC104D 사용설명서",
  summary:
    "순간온수 모듈 점검 문구가 표시되면 출수된 물을 음용하지 말고 전기 계통을 직접 수리하지 않은 채 상담합니다.",
  evidenceId: "EVD-JAC104D-MAN-P39-HOT-SAFETY",
  chunkId: "MAN-WPU-JAC104D-P39-HOT-WATER-SAFETY",
  documentId: "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00",
  documentVersion: "REV.00",
  page: 39,
  sectionTitle: "고장이라고 생각되면",
  riskLevel: "danger",
  safeActions: ["온수 사용 중지", "출수된 물 음용 중지"],
  prohibitedActions: ["전기 계통 직접 수리"],
  sourceLandingUrl:
    "https://www.skintellixservice.com/web/easy/easyMain.do?inputBasicKeyword=WPUJAC104DWH&tabIndex=3",
  sourceDirectDownloadUrl:
    "https://www.skintellixservice.com/common/fileDownloadS3.do?atchPath=cnts&atchNm=50f504a46a3843beb767baa6f9f94548&atchOrgNm=(rev00)%20WPU-JAC104%20(D)%2C%20JCC104%20(D)_User_KO_260428.pdf&atchExtNm=pdf",
};

function createInquiry(
  overrides: Partial<CounselorInquiry> &
    Pick<
      CounselorInquiry,
      | "id"
      | "scenarioId"
      | "customerId"
      | "customerName"
      | "symptomLabel"
      | "status"
      | "riskLevel"
      | "priority"
      | "updatedAt"
    >,
): CounselorInquiry {
  return {
    subscriptionId: overrides.customerId.replace("CUST", "SUB"),
    productCode: "WPUJAC104DWH",
    manualModel: "WPU-JAC104D",
    customerMessage: `${overrides.symptomLabel} 증상이 발생했습니다. 확인 부탁드립니다.`,
    conditions: "제품 사용 중 동일 증상이 반복되어 상담을 요청했습니다.",
    displayCode: "표시 문구 없음",
    performedAction: "제품 상태 확인 후 추가 사용을 중지했습니다.",
    actionResult: "증상이 계속되어 상담이 필요합니다.",
    requiresConsultation: false,
    feedbackResolved: false,
    createdAt: "2026-07-22T09:00:00+09:00",
    assignedCounselor: "한유진",
    managementType: "방문관리",
    serviceStartDate: "2026-02-15T09:00:00+09:00",
    lastCareDate: "2026-05-27T09:00:00+09:00",
    lastFilterDate: "2026-05-27T09:00:00+09:00",
    nextCareDate: "확인 필요",
    nextCareBasis: "team_designed",
    usageStatus: "NORMAL",
    usageMessage: "현재 사용 안내를 확인해 주세요.",
    restrictedWaterTypes: [],
    restrictedFunctions: [],
    guidanceBasis: "공식 매뉴얼과 고객 답변을 함께 확인합니다.",
    nextAction: "동일 증상 재발 시 상담을 요청해 주세요.",
    aiStatus: "COMPLETED",
    aiOutcome: "안전 안내 준비 완료",
    aiSummaryOriginal: `${overrides.symptomLabel} 문의입니다. 고객 원문과 공식 근거를 상담 전에 확인해야 합니다.`,
    stateVersion: 1,
    evidence: [OFFICIAL_EVIDENCE],
    timeline: [
      {
        title: "문의 접수",
        description: "고객 증상과 원문이 등록되었습니다.",
        actor: "고객",
        occurredAt: "2026-07-22 09:00",
      },
      {
        title: "AI 분석 완료",
        description: "공식 근거와 상담 필요 여부를 확인했습니다.",
        actor: "시스템",
        occurredAt: "2026-07-22 09:01",
      },
    ],
    ...overrides,
  };
}

// Mock: 개인 프로토타입 counselor.html의 v13 고정 상담 큐를 React 이관용으로 재현합니다.
export const COUNSELOR_INQUIRIES: readonly CounselorInquiry[] = [
  createInquiry({
    id: "DEMO-INQ-006",
    scenarioId: "SYN-JAC104-006",
    customerId: "DEMO-CUST-006",
    customerName: "합성 고객 006",
    symptomLabel: "온수 모듈 이상",
    status: "COMPLETION_PENDING",
    riskLevel: "DANGER",
    priority: "URGENT",
    requiresConsultation: true,
    feedbackResolved: true,
    feedbackComment: "점검 후 경고가 사라졌습니다.",
    customerMessage:
      "LCD에 순간온수 모듈 점검 문구가 표시되고 버튼이 깜박입니다.",
    conditions: "출수된 물은 마시지 않았고 전원을 분리했습니다.",
    displayCode: "순간온수 모듈 점검",
    performedAction: "출수된 물은 마시지 않았고 전원을 분리했습니다.",
    actionResult: "수행 결과 미입력",
    usageMessage: "현장 점검 후 일반 사용 가능으로 안내되었습니다.",
    guidanceBasis: "공식 매뉴얼 39쪽과 방문기사 현장 점검 결과",
    nextAction: "동일 경고 재발 시 사용을 중지하고 상담을 요청해주세요.",
    aiOutcome: "위험 규칙 감지",
    aiSummaryOriginal:
      "온수 모듈 이상 문의입니다. 고객 원문과 공식 근거 페이지를 상담 전에 확인해야 합니다.",
    updatedAt: "2026-07-22T14:20:00+09:00",
  }),
  createInquiry({
    id: "DEMO-INQ-004",
    scenarioId: "SYN-JAC104-004",
    customerId: "DEMO-CUST-004",
    customerName: "합성 고객 004",
    symptomLabel: "제품 누수",
    status: "VISIT_SCHEDULED",
    riskLevel: "DANGER",
    priority: "URGENT",
    requiresConsultation: true,
    usageStatus: "TOTAL_STOP",
    usageMessage: "안전을 위해 제품 전체 사용 중지를 유지해 주세요.",
    restrictedFunctions: ["전체 제품 사용"],
    updatedAt: "2026-07-22T12:20:00+09:00",
  }),
  createInquiry({
    id: "DEMO-INQ-003",
    scenarioId: "SYN-JAC104-003",
    customerId: "DEMO-CUST-003",
    customerName: "합성 고객 003",
    symptomLabel: "냉수 온도 이상",
    status: "CONSULTATION_IN_PROGRESS",
    riskLevel: "CAUTION",
    priority: "HIGH",
    requiresConsultation: true,
    updatedAt: "2026-07-22T11:20:00+09:00",
  }),
  createInquiry({
    id: "DEMO-INQ-005",
    scenarioId: "SYN-JAC104-005",
    customerId: "DEMO-CUST-005",
    customerName: "합성 고객 005",
    symptomLabel: "물맛·냄새 이상",
    status: "COMPLETION_PENDING",
    riskLevel: "CAUTION",
    priority: "HIGH",
    requiresConsultation: true,
    updatedAt: "2026-07-22T13:20:00+09:00",
  }),
  createInquiry({
    id: "DEMO-INQ-002",
    scenarioId: "SYN-JAC104-002",
    customerId: "DEMO-CUST-002",
    customerName: "합성 고객 002",
    symptomLabel: "출수량 저하",
    status: "CONSULTATION_REQUIRED",
    riskLevel: "GENERAL",
    priority: "NORMAL",
    requiresConsultation: true,
    updatedAt: "2026-07-22T10:20:00+09:00",
  }),
  createInquiry({
    id: "DEMO-INQ-001",
    scenarioId: "SYN-JAC104-001",
    customerId: "DEMO-CUST-001",
    customerName: "합성 고객 001",
    symptomLabel: "무출수",
    status: "QUESTIONNAIRE_IN_PROGRESS",
    riskLevel: "CAUTION",
    priority: "HIGH",
    updatedAt: "2026-07-22T09:20:00+09:00",
  }),
  createInquiry({
    id: "DEMO-INQ-007",
    scenarioId: "SYN-JAC104-007",
    customerId: "DEMO-CUST-007",
    customerName: "합성 고객 007",
    symptomLabel: "무출수 분석 실패",
    status: "QUESTIONNAIRE_IN_PROGRESS",
    riskLevel: "CAUTION",
    priority: "HIGH",
    aiStatus: "FAILED",
    aiOutcome: "AI 처리 실패",
    aiSummaryOriginal:
      "AI 요약을 생성하지 못했습니다. 고객 원문과 문진 답변을 직접 확인해 주세요.",
    evidence: [],
    updatedAt: "2026-07-22T15:20:00+09:00",
  }),
];
