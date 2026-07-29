import officialInquiryFixtures from "../../../../../data/synthetic/fixtures/inquiries.json";
import evidenceRegistrySource from "../../../../../data/processed/structured/evidence/jac104_evidence_registry.jsonl?raw";

import type {
  CounselorActionCode,
  CounselorAllowedAction,
  CounselorEvidence,
  CounselorInquiry,
  CounselorPriority,
  CounselorRisk,
  CounselorStatus,
} from "./consultantWorkspaceTypes";

interface OfficialInquiryFixture {
  inquiry_number: string;
  scenario_id: string;
  customer_id: string;
  subscription_id: string;
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

function getPriority(riskLevel: CounselorRisk): CounselorPriority {
  if (riskLevel === "DANGER") return "URGENT";
  if (riskLevel === "CAUTION") return "HIGH";
  return "NORMAL";
}

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
  const status = row.status as CounselorStatus;
  const riskLevel = row.risk_level.toUpperCase() as CounselorRisk;
  const usageStatus =
    row.usage_guidance_status as CounselorInquiry["usageStatus"];
  const presentation = TOPIC_PRESENTATION[row.topic_code] ?? {
    label: "기타 문의",
    displayCode: "상세 확인 필요",
  };
  const customerSequence = String(index + 1).padStart(3, "0");
  const feedbackResolved =
    status === "COMPLETION_PENDING" && row.assigned_role === "CONSULTANT";
  const evidence = getPublicEvidence(row.evidence_ids);
  const hasEvidence = evidence.length > 0;
  const requiresConsultation =
    usageStatus === "PENDING_CONSULTATION" ||
    status === "CONSULTATION_REQUIRED" ||
    status === "CONSULTATION_IN_PROGRESS" ||
    status === "VISIT_REVIEW_PENDING";

  return {
    id: row.inquiry_number,
    scenarioId: row.scenario_id,
    customerId: row.customer_id,
    customerName: `합성 고객 ${customerSequence}`,
    customerDisplayName: `합성 고객 ${customerSequence.slice(0, 1)}**`,
    subscriptionId: row.subscription_id,
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
    status,
    riskLevel,
    priority: getPriority(riskLevel),
    requiresConsultation,
    feedbackResolved,
    feedbackComment: feedbackResolved
      ? "상담 안내 후 증상이 해결되었다고 확인했습니다."
      : undefined,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    waitingMinutes: Math.max(
      0,
      Math.round(
        (new Date(row.updated_at).getTime() -
          new Date(row.created_at).getTime()) /
          60_000,
      ),
    ),
    assignedCounselor:
      row.assigned_role === "CONSULTANT"
        ? "한유진"
        : row.assigned_role === "TECHNICIAN"
          ? "방문기사 담당"
          : "미배정",
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
    nextAction:
      usageStatus === "PENDING_CONSULTATION"
        ? "임의 자가조치를 하지 말고 상담원 확인을 진행해 주세요."
        : "화면에 표시된 허용 행동만 진행해 주세요.",
    aiStatus: hasEvidence ? "COMPLETED" : "FAILED",
    aiOutcome: hasEvidence ? "공식 근거 확인 완료" : "근거 부족·상담 필요",
    aiSummaryOriginal: hasEvidence
      ? `${presentation.label} 문의입니다. 고객 원문과 공식 근거를 상담 전에 확인해야 합니다.`
      : "사용 가능한 근거가 없어 AI가 임의 안내를 생성하지 않았습니다.",
    stateVersion: row.state_version,
    allowedActions: getAllowedActions(
      status,
      row.assigned_role,
      feedbackResolved,
    ),
    evidence,
    timeline: [
      {
        title: "문의 접수",
        description: "공식 합성 fixture의 고객 문의가 접수되었습니다.",
        actor: "고객",
        occurredAt: row.created_at,
      },
      {
        title: hasEvidence ? "근거 확인 완료" : "근거 부족 감지",
        description: hasEvidence
          ? `${row.evidence_mode} 방식으로 공개 가능한 근거를 확인했습니다.`
          : "임의 안내를 생성하지 않고 상담 필요 상태로 전환했습니다.",
        actor: "시스템",
        occurredAt: row.updated_at,
      },
    ],
  };
}

// data/synthetic/fixtures/inquiries.json을 화면용 View Model로 변환한다.
// 프론트 Mock이 별도 시나리오 상태를 임의로 만들지 않도록 공식 fixture를 단일 원천으로 사용한다.
export const COUNSELOR_INQUIRIES: readonly CounselorInquiry[] = (
  officialInquiryFixtures as unknown as readonly OfficialInquiryFixture[]
).map(createInquiry);
