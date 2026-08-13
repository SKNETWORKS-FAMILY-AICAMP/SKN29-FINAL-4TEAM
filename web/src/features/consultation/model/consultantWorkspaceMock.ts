import officialInquiryFixtures from "../../../../../data/synthetic/fixtures/inquiries.json";
import officialCustomerFixtures from "../../../../../data/synthetic/fixtures/customer_profiles.json";
import officialSubscriptionFixtures from "../../../../../data/synthetic/fixtures/subscriptions.json";
import evidenceRegistrySource from "../../../../../data/processed/structured/evidence/jac104_evidence_registry.jsonl?raw";

import { getMockBackendInquiryProjection } from "../api/consultantWorkspaceMockProjection";

import {
  parseInquiryCode,
  parseInquiryId,
} from "../../../entities/inquiry/inquiryIdentifiers";

import type {
  CounselorActionCode,
  CounselorAllowedAction,
  CounselorEvidence,
  CounselorInquiry,
  CounselorStatus,
} from "./consultantWorkspaceTypes";
import {
  getCounselorWorkBucket,
  normalizeCounselorStatus,
} from "./consultantWorkspaceModel";

interface OfficialInquiryFixture {
  id: number;
  public_id: string;
  inquiry_number: string;
  scenario_id: string;
  customer_id: number;
  subscription_id: number;
  original_text: string;
  topic_code: string;
  variant: string;
  risk_level: string;
  usage_guidance_status: string;
  status: string;
  assigned_role: string;
  assigned_user_id: string | null;
  evidence_ids: readonly string[];
  evidence_mode: string;
  requires_fallback: boolean;
  state_version: number;
  created_at: string;
  updated_at: string;
}

interface OfficialPublicIdFixture {
  id: number;
  public_id: string;
}

interface OfficialEvidenceRegistryRow {
  evidence_id: string;
  product_model: string | null;
  version: string | null;
  page_refs: readonly number[];
  evidence_summary: string;
  source_url: string;
  verification_status: string;
  classification: string;
  allowed_use: string;
  rag_policy: string;
}

const ACTIONS = {
  START_CONSULTATION: {
    code: "START_CONSULTATION",
    label: "상담 시작",
    operationId: "startConsultation",
    style: "PRIMARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  UPDATE_CONSULTATION_SUMMARY: {
    code: "UPDATE_CONSULTATION_SUMMARY",
    label: "상담 요약 수정",
    operationId: "updateConsultationSummary",
    style: "SECONDARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  CONFIRM_CONSULTATION_SUMMARY: {
    code: "CONFIRM_CONSULTATION_SUMMARY",
    label: "상담 요약 확정",
    operationId: "confirmConsultationSummary",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "수정한 상담 요약을 확정하시겠습니까?",
  },
  CONSULTATION_COMPLETED: {
    code: "CONSULTATION_COMPLETED",
    label: "상담 처리 완료",
    operationId: "completeConsultation",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "상담 처리를 완료하고 고객 확인 단계로 전환하시겠습니까?",
  },
  VISIT_REVIEW_REQUIRED: {
    code: "VISIT_REVIEW_REQUIRED",
    label: "방문 필요 여부 검토",
    operationId: "requestVisitReview",
    style: "SECONDARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  VISIT_NEEDED: {
    code: "VISIT_NEEDED",
    label: "방문 필요 확정",
    operationId: "createVisitRequest",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "방문 요청을 생성하시겠습니까?",
  },
  VISIT_NOT_NEEDED: {
    code: "VISIT_NOT_NEEDED",
    label: "방문 불필요 확정",
    operationId: "markVisitNotNeeded",
    style: "SECONDARY",
    requiresConfirmation: true,
    confirmationMessage: "방문 없이 상담 처리 결과 확인 단계로 전환하시겠습니까?",
  },
  UPDATE_VISIT_SCHEDULE: {
    code: "UPDATE_VISIT_SCHEDULE",
    label: "방문 일정 조율",
    operationId: "updateVisitSchedule",
    style: "SECONDARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  CONFIRM_VISIT: {
    code: "CONFIRM_VISIT",
    label: "방문 일정 확정",
    operationId: "confirmVisit",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "담당 기사와 방문 일정을 확정하시겠습니까?",
  },
  RESUME_CONSULTATION: {
    code: "RESUME_CONSULTATION",
    label: "상담 대기열로 복귀",
    operationId: "resumeConsultation",
    style: "PRIMARY",
    requiresConfirmation: false,
    confirmationMessage: null,
  },
  FINALIZE_INQUIRY: {
    code: "FINALIZE_INQUIRY",
    label: "문의 최종 완료",
    operationId: "finalizeInquiry",
    style: "PRIMARY",
    requiresConfirmation: true,
    confirmationMessage: "고객 해결 확인을 검토하고 문의를 최종 완료하시겠습니까?",
  },
} as const satisfies Record<CounselorActionCode, CounselorAllowedAction>;

const EVIDENCE_REGISTRY = new Map(
  evidenceRegistrySource
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line) as OfficialEvidenceRegistryRow)
    .map((item) => [item.evidence_id, item] as const),
);

const TOPIC_PRESENTATION: Record<
  string,
  { label: string; extra?: string; displayCode: string }
> = {
  symptom_no_water: {
    label: "무출수",
    extra: "출수 불가",
    displayCode: "물이 나오지 않음",
  },
  symptom_low_flow: {
    label: "출수량 저하",
    extra: "출수 시간 증가",
    displayCode: "물줄기 약함",
  },
  symptom_cold_temperature: {
    label: "냉수 온도 이상",
    extra: "냉수 성능 저하",
    displayCode: "냉수가 덜 차가움",
  },
  symptom_leak: {
    label: "제품 누수",
    extra: "바닥 물기",
    displayCode: "제품 주변 누수",
  },
  symptom_taste_odor: {
    label: "물맛·냄새 이상",
    extra: "음용 품질 이상",
    displayCode: "맛 또는 냄새 이상",
  },
  symptom_hot_water_safety: {
    label: "온수 모듈 이상",
    extra: "온수 안전 경고",
    displayCode: "온수 모듈 점검 필요",
  },
  symptom_noise: {
    label: "제품 소음",
    extra: "이상 진동",
    displayCode: "평소와 다른 소음",
  },
  capability_iot_unsupported: {
    label: "IoT 기능 지원 문의",
    extra: "지원 범위 확인",
    displayCode: "지원하지 않는 기능",
  },
};

const KOREAN_SURNAMES = [
  "김",
  "이",
  "박",
  "최",
  "정",
  "강",
  "조",
  "윤",
  "장",
  "임",
] as const;

const KOREAN_GIVEN_NAMES = [
  "민준",
  "서연",
  "도윤",
  "지우",
  "현우",
  "하윤",
  "준서",
  "수아",
  "지훈",
  "채원",
  "건우",
  "예은",
] as const;

function getPreviewCustomerName(index: number): string {
  const surname = KOREAN_SURNAMES[index % KOREAN_SURNAMES.length];
  const givenName =
    KOREAN_GIVEN_NAMES[
      Math.floor(index / KOREAN_SURNAMES.length) % KOREAN_GIVEN_NAMES.length
    ];
  return `${surname}${givenName}`;
}

function getAllowedActions(
  status: CounselorStatus,
  assignedRole: string,
  feedbackResolved: boolean,
): readonly CounselorAllowedAction[] {
  if (assignedRole !== "CONSULTANT") return [];

  const byStatus: Partial<
    Record<CounselorStatus, readonly CounselorAllowedAction[]>
  > = {
    CONSULTATION_REQUIRED: [ACTIONS.START_CONSULTATION],
    CONSULTATION_IN_PROGRESS: [
      ACTIONS.UPDATE_CONSULTATION_SUMMARY,
      ACTIONS.CONFIRM_CONSULTATION_SUMMARY,
      ACTIONS.CONSULTATION_COMPLETED,
      ACTIONS.VISIT_REVIEW_REQUIRED,
    ],
    VISIT_REVIEW_PENDING: [ACTIONS.VISIT_NEEDED, ACTIONS.VISIT_NOT_NEEDED],
    VISIT_SCHEDULING: [ACTIONS.UPDATE_VISIT_SCHEDULE, ACTIONS.CONFIRM_VISIT],
    REVISIT_REQUIRED: [ACTIONS.UPDATE_VISIT_SCHEDULE],
    REOPENED: [ACTIONS.RESUME_CONSULTATION],
    COMPLETION_PENDING: feedbackResolved ? [ACTIONS.FINALIZE_INQUIRY] : [],
  };

  return byStatus[status] ?? [];
}

export function getConsultantAllowedActions(
  status: CounselorStatus,
  feedbackResolved = false,
): readonly CounselorAllowedAction[] {
  return getAllowedActions(status, "CONSULTANT", feedbackResolved);
}

const CUSTOMER_PUBLIC_IDS = new Map(
  (officialCustomerFixtures as readonly OfficialPublicIdFixture[]).map(
    (row) => [row.id, row.public_id],
  ),
);

const SUBSCRIPTION_PUBLIC_IDS = new Map(
  (officialSubscriptionFixtures as readonly OfficialPublicIdFixture[]).map(
    (row) => [row.id, row.public_id],
  ),
);

function getUsageMessage(status: CounselorInquiry["usageStatus"]): string {
  if (status === "TOTAL_STOP") {
    return "안전을 위해 제품 전체 사용을 중지하고 상담원의 안내를 기다려 주세요.";
  }
  if (status === "PARTIAL_STOP") {
    return "안내된 출수·기능만 중지하고 증상 변화를 확인해 주세요.";
  }
  if (status === "PENDING_CONSULTATION") {
    return "확인 가능한 근거가 부족하므로 임의 조치 없이 상담원 확인이 필요합니다.";
  }
  return "현재 확인된 범위에서는 일반 사용이 가능합니다.";
}

function getPublicEvidence(
  evidenceIds: readonly string[],
): readonly CounselorEvidence[] {
  return evidenceIds.flatMap((evidenceId) => {
    const source = EVIDENCE_REGISTRY.get(evidenceId);
    const page = source?.page_refs[0];

    if (
      !source ||
      source.allowed_use !== "MVP" ||
      source.rag_policy !== "INCLUDE" ||
      page === undefined
    ) {
      return [];
    }

    const dataClassification = [
      "official",
      "team_designed",
      "synthetic",
    ].includes(source.classification)
      ? (source.classification as CounselorEvidence["dataClassification"])
      : "official";

    return [
      {
        documentTitle: `${source.product_model ?? "WPU-JAC104D"} 사용설명서`,
        summary: source.evidence_summary,
        documentVersion: source.version ?? "버전 미표기",
        page,
        verificationLabel:
          source.verification_status === "TEXT_AND_VISUAL_VERIFIED"
            ? "텍스트·시각 검증 완료"
            : "검증 상태 확인 필요",
        dataClassification,
        sourceLandingUrl: source.source_url,
      },
    ];
  });
}

function createInquiry(
  row: OfficialInquiryFixture,
  index: number,
): CounselorInquiry {
  const originalStatus = normalizeCounselorStatus(row.status);
  const projection = getMockBackendInquiryProjection(row.scenario_id);
  const allowedActions = projection.allowedActionCodes.map(
    (code) => ACTIONS[code],
  );
  const isRoutingPending = ["DRAFT", "QUESTIONNAIRE_IN_PROGRESS"].includes(
    originalStatus,
  );
  const usageStatus =
    row.usage_guidance_status as CounselorInquiry["usageStatus"];
  const presentation = TOPIC_PRESENTATION[row.topic_code] ?? {
    label: "기타 문의",
    displayCode: "상세 확인 필요",
  };
  const customerName = getPreviewCustomerName(index);
  const evidence = getPublicEvidence(row.evidence_ids);
  const hasEvidence = evidence.length > 0;

  return {
    inquiryId: parseInquiryId(row.public_id),
    inquiryCode: parseInquiryCode(row.inquiry_number),
    scenarioId: row.scenario_id,
    customerId: CUSTOMER_PUBLIC_IDS.get(row.customer_id) ?? "공개 고객 ID 확인 필요",
    customerName,
    customerDisplayName: customerName,
    customerPhone: `010-****-${String(1200 + index).slice(-4)} (합성)`,
    serviceAddress: "서울특별시 마포구 월드컵북로 ** (합성)",
    warrantyLabel: "무상보증 · 2027.02까지",
    previousVisitCount: index % 3,
    subscriptionId:
      SUBSCRIPTION_PUBLIC_IDS.get(row.subscription_id) ?? "공개 구독 ID 확인 필요",
    productCode: "WPUJAC104DWH",
    manualModel: "WPU-JAC104D",
    symptomLabel: presentation.label,
    symptomLabels: presentation.extra
      ? [presentation.label, presentation.extra]
      : [presentation.label],
    customerMessage: row.original_text,
    conditions: `${row.variant} 조건의 공식 합성 시나리오입니다.`,
    displayCode: presentation.displayCode,
    performedAction: "고객 입력과 현재 제품 상태를 확인했습니다.",
    actionResult: "현재 상태와 허용 행동을 기준으로 다음 처리를 진행합니다.",
    status: projection.status,
    riskLevel: projection.riskLevel,
    priority: projection.priority,
    routingTarget: projection.routingTarget,
    routingReason: projection.routingReason,
    requiresConsultation: projection.requiresConsultation,
    feedbackResolved: projection.feedbackResolved,
    feedbackComment: projection.feedbackResolved
      ? "상담 안내 후 증상이 해결되었다고 확인했습니다."
      : undefined,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    waitingMinutes: projection.waitingMinutes,
    assignedCounselor: projection.assignedCounselor,
    managementType: "방문관리",
    serviceStartDate: "2026-02-15T09:00:00+09:00",
    lastCareDate: "2026-05-27T09:00:00+09:00",
    lastFilterDate: "2026-05-27T09:00:00+09:00",
    nextCareDate: "확인 필요",
    nextCareBasis: "team_designed",
    usageStatus,
    usageMessage: getUsageMessage(usageStatus),
    restrictedWaterTypes:
      usageStatus === "PARTIAL_STOP" ? ["증상 관련 출수"] : [],
    restrictedFunctions:
      usageStatus === "TOTAL_STOP" ? ["제품 전체 사용"] : [],
    guidanceBasis: !hasEvidence
      ? "사용 가능한 공식 근거가 없어 상담 확인 전까지 안내를 보류합니다."
      : row.requires_fallback
        ? "일부 공식 근거만 확인되어 상담원이 적용 범위를 추가 확인해야 합니다."
        : "공식 설명서와 고객 입력을 함께 확인했습니다.",
    nextAction: projection.routingReason,
    aiStatus: hasEvidence ? "COMPLETED" : "FAILED",
    aiOutcome: hasEvidence ? "공식 근거 확인 완료" : "근거 부족·상담 필요",
    aiSummaryOriginal: hasEvidence
      ? `${presentation.label} 문의입니다. 고객 원문과 공식 근거를 상담 전에 확인해야 합니다.`
      : "사용 가능한 근거가 없어 AI가 임의 안내를 생성하지 않았습니다.",
    stateVersion: row.state_version,
    allowedActions,
    evidence,
    timeline: [
      {
        title: "문의 접수",
        description: "공식 합성 fixture의 고객 문의가 접수되었습니다.",
        actor: "고객",
        occurredAt: row.created_at,
      },
      {
        title:
          isRoutingPending
            ? "AI 담당 분류 대기"
            : projection.routingTarget === "FIELD_TECHNICIAN"
            ? "AI 방문기사 자동 인계"
            : "상담사 확인 필요 분류",
        description: isRoutingPending
          ? "문진 완료 후 위험도 기준으로 담당자를 결정합니다."
          : projection.routingReason,
        actor: "AI",
        occurredAt: row.updated_at,
      },
      {
        title: hasEvidence ? "근거 확인 완료" : "근거 부족 감지",
        description: hasEvidence
          ? `${row.evidence_mode} 방식으로 공개 가능한 근거를 확인했습니다.`
          : "사용 가능한 공식 근거가 없어 근거 부족 상태를 기록했습니다.",
        actor: "시스템",
        occurredAt: row.updated_at,
      },
    ],
  };
}

const BASE_COUNSELOR_INQUIRIES: readonly CounselorInquiry[] = (
  officialInquiryFixtures as unknown as readonly OfficialInquiryFixture[]
).map(createInquiry);

const CONSULTANT_VISIBLE_STATUSES = new Set<CounselorStatus>([
  "CONSULTATION_REQUIRED",
  "CONSULTATION_IN_PROGRESS",
  "VISIT_REVIEW_PENDING",
  "VISIT_SCHEDULING",
  "VISIT_SCHEDULED",
  "COMPLETION_PENDING",
  "REVISIT_REQUIRED",
  "REOPENED",
  "RESOLVED",
  "CANCELLED",
]);

const CONSULTANT_BUCKET_TARGETS = {
  NEW: 30,
  IN_PROGRESS: 30,
  COMPLETED: 30,
} as const;

const RISK_SECTION_TARGETS = [
  {
    riskLevel: "DANGER",
    priority: "URGENT",
    routingReason: "긴급 문의는 상담사가 안전 안내를 먼저 확인합니다.",
  },
  {
    riskLevel: "CAUTION",
    priority: "HIGH",
    routingReason: "주의 문의는 상담사가 안내 내용을 먼저 확인합니다.",
  },
  {
    riskLevel: "GENERAL",
    priority: "NORMAL",
    routingReason: "일반 문의의 상담 현황을 확인합니다.",
  },
] as const satisfies readonly {
  riskLevel: Exclude<CounselorInquiry["riskLevel"], "UNKNOWN">;
  priority: Exclude<CounselorInquiry["priority"], "UNKNOWN">;
  routingReason: string;
}[];

const RISK_SECTION_TARGET_COUNT = 10;

const SUPPLEMENTAL_CUSTOMER_MESSAGES = [
  "출수 버튼을 눌러도 물이 바로 나오지 않고 잠시 뒤에 조금씩 나옵니다.",
  "제품 아래쪽에 물기가 보여 안전하게 사용할 수 있는지 확인하고 싶습니다.",
  "평소보다 큰 소음과 진동이 반복되어 점검이 필요한지 문의드립니다.",
  "냉수 온도가 평소보다 높고 표시창의 온도도 자주 바뀝니다.",
  "필터 교체 후 물맛이 달라져 추가 확인을 요청드립니다.",
  "온수 기능을 사용한 뒤 점검 안내가 표시되어 사용을 멈췄습니다.",
] as const;

function isConsultantQueueInquiry(inquiry: CounselorInquiry): boolean {
  return (
    inquiry.routingTarget === "CONSULTANT" &&
    CONSULTANT_VISIBLE_STATUSES.has(inquiry.status)
  );
}

function createSupplementalConsultantInquiries(
  baseQueue: readonly CounselorInquiry[],
): readonly CounselorInquiry[] {
  let sequence = 1;

  return (Object.keys(CONSULTANT_BUCKET_TARGETS) as Array<
    keyof typeof CONSULTANT_BUCKET_TARGETS
  >).flatMap((bucket) => {
    const templates = baseQueue.filter(
      (inquiry) => getCounselorWorkBucket(inquiry.status) === bucket,
    );

    return RISK_SECTION_TARGETS.flatMap((riskTarget, riskIndex) => {
      const currentCount = templates.filter(
        (inquiry) => inquiry.riskLevel === riskTarget.riskLevel,
      ).length;
      const requiredCount = Math.max(
        0,
        RISK_SECTION_TARGET_COUNT - currentCount,
      );

      return Array.from({ length: requiredCount }, (_, riskItemIndex) => {
        const template =
          templates[(riskIndex + riskItemIndex) % templates.length];
        const mockSequence = sequence++;
        const customerSequence = String(100 + mockSequence).padStart(3, "0");
        const customerName = getPreviewCustomerName(
          BASE_COUNSELOR_INQUIRIES.length + mockSequence - 1,
        );
        const idSuffix = String(mockSequence).padStart(12, "0");
        const receivedDay = String(10 - (mockSequence % 7)).padStart(2, "0");
        const receivedHour = String(8 + (mockSequence % 10)).padStart(2, "0");
        const receivedAt = `2026-08-${receivedDay}T${receivedHour}:00:00+09:00`;

        return {
          ...template,
          inquiryId: parseInquiryId(
            `20000000-0000-4000-8000-${idSuffix}`,
          ),
          inquiryCode: parseInquiryCode(
            `INQ-20260810-${String(100 + mockSequence).padStart(4, "0")}`,
          ),
          scenarioId: `${template.scenarioId}-web-mock-${mockSequence}`,
          customerId: `SYN-CUSTOMER-${customerSequence}`,
          customerName,
          customerDisplayName: customerName,
          customerPhone: `010-****-${String(3200 + mockSequence).slice(-4)} (합성)`,
          subscriptionId: `SYN-SUBSCRIPTION-${customerSequence}`,
          customerMessage:
            SUPPLEMENTAL_CUSTOMER_MESSAGES[
              (mockSequence - 1) % SUPPLEMENTAL_CUSTOMER_MESSAGES.length
            ],
          conditions: `${bucket} 업무함 확인을 위한 확장 Mock 시나리오입니다.`,
          riskLevel: riskTarget.riskLevel,
          priority: riskTarget.priority,
          routingTarget: "CONSULTANT",
          routingReason: riskTarget.routingReason,
          requiresConsultation: true,
          createdAt: receivedAt,
          updatedAt: receivedAt,
          waitingMinutes: 8 + mockSequence * 3,
          previousVisitCount: mockSequence % 3,
          stateVersion: 1 + (mockSequence % 4),
          timeline: template.timeline.map((item) => ({
            ...item,
            occurredAt: receivedAt,
          })),
        };
      });
    });
  });
}

const BASE_CONSULTANT_QUEUE_INQUIRIES = BASE_COUNSELOR_INQUIRIES.filter(
  isConsultantQueueInquiry,
);

const SUPPLEMENTAL_CONSULTANT_INQUIRIES =
  createSupplementalConsultantInquiries(BASE_CONSULTANT_QUEUE_INQUIRIES);

// 공식 fixture를 유지하고 상담사 화면의 업무량 확인용 합성 문의를 추가한다.
// 화면에서는 상태·위험도·우선순위·담당자·허용 행동을 다시 계산하지 않는다.
export const COUNSELOR_INQUIRIES: readonly CounselorInquiry[] = [
  ...BASE_COUNSELOR_INQUIRIES,
  ...SUPPLEMENTAL_CONSULTANT_INQUIRIES,
];

// 상담사 화면 디자인 검증용 Mock에서는 각 업무함의 일반·주의·긴급 문의를 10건씩 노출한다.
// 실제 Remote 연동에서는 Backend가 전달한 배정·위험도 결과를 그대로 사용한다.
export const CONSULTANT_QUEUE_INQUIRIES: readonly CounselorInquiry[] =
  COUNSELOR_INQUIRIES.filter(isConsultantQueueInquiry);

const REMOTE_PARITY_TEMPLATE = CONSULTANT_QUEUE_INQUIRIES.find(
  (inquiry) =>
    getCounselorWorkBucket(inquiry.status) === "NEW" &&
    inquiry.riskLevel === "GENERAL",
);

if (!REMOTE_PARITY_TEMPLATE) {
  throw new Error("CONS-04 Remote parity Mock의 기준 문의를 찾을 수 없습니다.");
}

// 로컬 Backend에 cons04-phone-inquiry-v1만 적재했을 때의 목록 응답과
// 같은 화면을 확인하기 위한 기본 Mock이다. 공개·합성 정보만 포함한다.
export const REMOTE_PARITY_CONSULTANT_INQUIRIES: readonly CounselorInquiry[] = [
  {
    ...REMOTE_PARITY_TEMPLATE,
    inquiryCode: parseInquiryCode("INQ-MOCK-CONS04-0001"),
    customerName: "합성 전화문의 고객 001",
    customerDisplayName: "합성 전화문의 고객 00*",
    customerPhone: "010-****-1204 (합성)",
    customerMessage: "정수기 하단에서 물이 새는 것 같습니다.",
    symptomLabel: "제품 누수",
    symptomLabels: ["제품 누수", "바닥 물기"],
    displayCode: "제품 주변 누수",
    status: "CONSULTATION_REQUIRED",
    riskLevel: "GENERAL",
    priority: "NORMAL",
    routingTarget: "CONSULTANT",
    requiresConsultation: true,
    stateVersion: 1,
    allowedActions: [],
  },
];
