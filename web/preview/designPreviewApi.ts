import type {
  AllowedActionDto,
  ConsultantInquiryDetailDto,
  ConsultantInquiryListDataDto,
  ConsultantInquiryListItemDto,
  ConsultantInquiryStatusDto,
  ConsultantPriorityDto,
  ConsultantRiskLevelDto,
  UnassignedConsultationQueueDataDto,
  UnassignedConsultationQueueItemDto,
} from "../src/features/consultation/api/consultantWorkspaceRemoteTypes.ts";
import { MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA } from "../src/features/notice/model/consultantNotice.ts";

export interface DesignPreviewRequest {
  url: string;
  method: string;
  body?: unknown;
  headers?: Record<string, string>;
}

export interface DesignPreviewResponse {
  status: number;
  body: {
    success: boolean;
    data: unknown;
    error: { code: string; message: string; details: Record<string, unknown> } | null;
    metadata: { correlation_id: string };
  };
}

const inquiryId = (index: number) =>
  `90000000-0000-4000-8000-${String(index).padStart(12, "0")}`;

export const DESIGN_PREVIEW_INQUIRY_IDS = {
  new: inquiryId(1),
  inProgress: inquiryId(4),
  completed: inquiryId(12),
  unassigned: inquiryId(16),
  visit: inquiryId(8),
} as const;

export const DESIGN_PREVIEW_READ_ONLY_MESSAGE =
  "로컬 디자인 미리보기에서는 저장·배정·상태 변경을 실행하지 않습니다. 처리 중인 샘플 문의에서 입력 화면을 확인해 주세요. 운영 데이터에는 영향이 없습니다.";

interface PreviewInquiry {
  detail: ConsultantInquiryDetailDto;
  unassigned: boolean;
  waitingSeconds: number;
}

const PRODUCTS = [
  { code: "WPUJAC104DWH", name: "초소형 직수 냉온 정수기" },
  { code: "WPUIAC425", name: "원코크 플러스 얼음물 정수기" },
  { code: "WPUIAC606", name: "MEGA ICE mini 얼음 냉온정수기" },
] as const;

const CUSTOMER_NAMES = [
  "김민준", "이서연", "박도윤", "최지우", "정하윤",
  "강준서", "조수아", "윤지훈", "장채원", "임건우",
  "김예은", "이현우", "박서윤", "최유진", "정시우",
  "강유나", "조지호", "윤하린", "장서준",
] as const;

const SYMPTOMS = [
  "정수기 물줄기가 평소보다 약해졌어요",
  "제품 아래쪽에 물이 고여 있어요",
  "지난 상담 이후 같은 소리가 다시 들려요",
  "필터 교체 시기와 관리 방법을 확인하고 싶어요",
  "얼음이 만들어지는 시간이 길어졌어요",
  "온수 선택 후 표시등이 계속 깜빡여요",
  "출수량이 줄어 방문 점검이 필요해요",
  "정수기 점검 방문 일정을 조정하고 싶어요",
  "예약한 방문 일정을 확인해 주세요",
  "상담 안내대로 확인한 후 정상적으로 작동해요",
  "점검 이후에도 같은 증상이 있어 재방문을 요청해요",
  "출수 버튼 사용 방법 문의",
  "얼음 보관함 관리 방법 문의",
  "필터 교체 알림 확인 방법 문의",
  "중복으로 접수한 문의를 취소했어요",
  "냉수가 충분히 차갑지 않아요",
  "제품 근처에서 평소와 다른 냄새가 나요",
  "정수기 사용 중 소음이 들려요",
  "얼음 출수 버튼이 반응하지 않아요",
] as const;

const ASSIGNED_STATUSES: readonly ConsultantInquiryStatusDto[] = [
  "CONSULTATION_REQUIRED", "CONSULTATION_REQUIRED", "REOPENED",
  "CONSULTATION_IN_PROGRESS", "CONSULTATION_IN_PROGRESS", "CONSULTATION_IN_PROGRESS",
  "VISIT_REVIEW_PENDING", "VISIT_SCHEDULING", "VISIT_SCHEDULED",
  "COMPLETION_PENDING", "REVISIT_REQUIRED", "RESOLVED", "RESOLVED", "RESOLVED", "CANCELLED",
];

function action(code: string, label: string, operationId: string): AllowedActionDto {
  return {
    code,
    label,
    operation_id: operationId,
    style: "PRIMARY",
    requires_confirmation: false,
    confirmation_message: null,
  };
}

// These are sample server snapshots, not a client implementation of business rules.
function sampleActions(status: ConsultantInquiryStatusDto, index: number, unassigned: boolean) {
  if (unassigned) return [action("CLAIM_CONSULTATION", "상담 시작", "claimConsultation")];
  switch (status) {
    case "CONSULTATION_REQUIRED":
      return [action("START_CONSULTATION", "상담 시작", "startConsultation")];
    case "REOPENED":
      return [action("RESUME_CONSULTATION", "상담 재개", "resumeConsultation")];
    case "CONSULTATION_IN_PROGRESS":
      return [
        action("UPDATE_CONSULTATION_SUMMARY", "상담 내용 수정", "updateConsultationSummary"),
        index === 5
          ? action("CONSULTATION_COMPLETED", "상담 완료", "completeConsultation")
          : action("CONFIRM_CONSULTATION_SUMMARY", "상담 내용 확정", "confirmConsultationSummary"),
        action("VISIT_REVIEW_REQUIRED", "방문 검토", "requestVisitReview"),
      ];
    case "VISIT_REVIEW_PENDING":
      return [
        action("VISIT_NEEDED", "방문 필요", "createVisit"),
        action("VISIT_NOT_NEEDED", "방문 불필요", "markVisitNotNeeded"),
      ];
    case "VISIT_SCHEDULING":
      return [
        action("UPDATE_VISIT_SCHEDULE", "기사·일정 저장", "updateVisitSchedule"),
        action("CONFIRM_VISIT", "방문 확정", "confirmVisit"),
      ];
    case "COMPLETION_PENDING":
      return [action("FINALIZE_INQUIRY", "최종 완료", "finalizeInquiry")];
    default:
      return [];
  }
}

function createSampleInquiry(index: number): PreviewInquiry {
  const unassigned = index > ASSIGNED_STATUSES.length;
  const status = ASSIGNED_STATUSES[index - 1] ?? "CONSULTATION_REQUIRED";
  const product = PRODUCTS[(index - 1) % PRODUCTS.length];
  const riskLevel: ConsultantRiskLevelDto = index % 3 === 2 ? "danger" : index % 3 === 0 ? "caution" : "general";
  const priority: ConsultantPriorityDto = riskLevel === "danger" ? "URGENT" : riskLevel === "caution" ? "HIGH" : "NORMAL";
  const usageStatus = riskLevel === "danger" ? "TOTAL_STOP" : "NORMAL";
  const receivedAt = `2026-08-${String(31 - Math.floor((index - 1) / 4)).padStart(2, "0")}T09:${String(index).padStart(2, "0")}:00+09:00`;
  const updatedAt = receivedAt.replace("T09:", "T10:");
  const stateVersion = index + 2;
  const hasConsultation = !unassigned && status !== "CONSULTATION_REQUIRED";
  const hasVisit = ["VISIT_SCHEDULING", "VISIT_SCHEDULED", "REVISIT_REQUIRED"].includes(status);
  const hasConfirmedSummary = hasConsultation && (index === 5 || status !== "CONSULTATION_IN_PROGRESS");
  const summary = `고객의 문의 내용과 제품 상태를 확인했습니다. ${SYMPTOMS[index - 1]}에 대한 상담 화면 미리보기입니다.`;
  const technician = MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA.technicians[0];
  const id = inquiryId(index);
  return {
    unassigned,
    waitingSeconds: (20 - index) * 300,
    detail: {
      inquiry: {
        inquiry_id: id,
        inquiry_code: `PREVIEW-${String(index).padStart(4, "0")}`,
        status,
        state_version: stateVersion,
        risk_level: riskLevel,
        priority,
        received_at: receivedAt,
        updated_at: updatedAt,
      },
      customer: {
        is_synthetic: true,
        display_name: CUSTOMER_NAMES[index - 1],
        phone: `010-0000-${String(index).padStart(4, "0")}`,
        phone_masked: `010-****-${String(index).padStart(4, "0")}`,
        contact_phone: null,
      },
      product_and_care: {
        product_model: product.code,
        product_model_name: product.name,
        subscription_status: "ACTIVE",
        management_type: index % 2 === 0 ? "VISIT_CARE" : "SELF_CARE",
        recent_care_date: "2026-07-20",
      },
      symptom_and_questionnaire: {
        symptom_summary: SYMPTOMS[index - 1],
        answers: [
          { question_code: "PREVIEW_START", question_text: "증상이 언제부터 발생했나요?", answer: "어제부터 증상이 나타났습니다." },
          { question_code: "PREVIEW_REPEATED", question_text: "같은 증상이 반복되나요?", answer: "제품을 사용할 때 간헐적으로 나타납니다." },
        ],
      },
      guidance_and_actions: {
        usage_guidance_status: usageStatus,
        usage_guidance_display_label: usageStatus === "TOTAL_STOP" ? "제품 사용 중단" : "정상 사용 가능",
        usage_guidance_message: "제품 상태와 고객이 확인한 내용을 살펴본 후 상담을 진행합니다. 이 내용은 화면 확인용 샘플입니다.",
        restricted_functions: usageStatus === "TOTAL_STOP" ? ["전체 기능"] : [],
      },
      consultation: hasConsultation ? {
        consultation_id: `preview-consultation-${index}`,
        result_code: hasVisit || status === "VISIT_REVIEW_PENDING" ? "VISIT_REQUIRED" : status === "RESOLVED" || status === "COMPLETION_PENDING" ? "COMPLETED_NO_VISIT" : "PENDING",
        summary: {
          ai_draft_summary: summary,
          edited_summary: summary,
          confirmed_summary: hasConfirmedSummary ? summary : null,
          confirmed_at: hasConfirmedSummary ? updatedAt : null,
        },
        consultation_note: "고객이 확인한 증상과 발생 시점을 기록하고 제품 사용 상태를 함께 확인했습니다.",
        additional_check: "같은 증상이 반복되는지 확인하기로 했습니다.",
        customer_guidance: "상담 내용을 정리하여 고객에게 안내했습니다.",
        usage_guidance_status: usageStatus,
      } : null,
      visit: hasVisit ? {
        visit_id: `preview-visit-${index}`,
        inquiry_id: id,
        schedule: {
          preferred_date: "2026-09-02",
          confirmed_date: status === "VISIT_SCHEDULING" ? null : "2026-09-02",
          schedule_status: status === "VISIT_SCHEDULING" ? "SCHEDULING" : status === "REVISIT_REQUIRED" ? "FOLLOW_UP_REQUIRED" : "CONFIRMED",
          synthetic_technician_id: technician.userId,
        },
        technician: {
          is_synthetic: true,
          technician_id: technician.userId,
          display_name: technician.name,
          phone: technician.phone,
        },
      } : null,
      state_history: [
        { from_status: null, to_status: "CONSULTATION_REQUIRED", changed_at: receivedAt, actor_role: "SYSTEM" },
        ...(hasConsultation ? [{
          from_status: "CONSULTATION_REQUIRED",
          to_status: status,
          changed_at: updatedAt,
          actor_role: "CONSULTANT" as const,
        }] : []),
      ],
      workflow: { status, state_version: stateVersion, allowed_actions: sampleActions(status, index, unassigned) },
      section_errors: [],
    },
  };
}

function listItem(sample: PreviewInquiry): ConsultantInquiryListItemDto {
  const detail = sample.detail;
  const name = detail.customer.display_name;
  return {
    ...detail.inquiry,
    symptom_summary: detail.symptom_and_questionnaire.symptom_summary,
    customer_display_name_masked: `${name[0]}*${name.slice(2)}`,
    product_model: detail.product_and_care!.product_model,
    current_assignee_type: "CONSULTANT",
    waiting_seconds: sample.waitingSeconds,
    allowed_actions: detail.workflow.allowed_actions,
  };
}

function filteredSamples(samples: readonly PreviewInquiry[], params: URLSearchParams) {
  const search = params.get("q")?.trim().toLocaleLowerCase();
  const values = (key: string) => params.getAll(key).flatMap((value) => value.split(","));
  const statuses = values("status");
  const risks = values("risk_level");
  const priorities = values("priority");
  const from = params.get("from");
  const to = params.get("to");
  const filtered = samples.filter(({ detail }) => {
    const inquiry = detail.inquiry;
    return (!search || [inquiry.inquiry_code, detail.customer.display_name, detail.symptom_and_questionnaire.symptom_summary].join(" ").toLocaleLowerCase().includes(search))
      && (!statuses.length || statuses.includes(inquiry.status))
      && (!risks.length || risks.includes(inquiry.risk_level))
      && (!priorities.length || priorities.includes(inquiry.priority))
      && (!from || inquiry.received_at.slice(0, 10) >= from)
      && (!to || inquiry.received_at.slice(0, 10) <= to);
  });
  const riskRank = { general: 0, caution: 1, danger: 2 };
  return filtered.sort((left, right) => {
    switch (params.get("sort")) {
      case "WAITING_DESC": return right.waitingSeconds - left.waitingSeconds;
      case "RISK_DESC": return riskRank[right.detail.inquiry.risk_level] - riskRank[left.detail.inquiry.risk_level];
      case "UPDATED_ASC": return left.detail.inquiry.updated_at.localeCompare(right.detail.inquiry.updated_at);
      default: return right.detail.inquiry.updated_at.localeCompare(left.detail.inquiry.updated_at);
    }
  });
}

function positiveInt(value: string | null, fallback: number, maximum: number) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? Math.min(parsed, maximum) : fallback;
}

function paginate<T>(items: readonly T[], params: URLSearchParams) {
  const page = positiveInt(params.get("page"), 1, 10000);
  const size = positiveInt(params.get("size"), 20, 100);
  return {
    items: items.slice((page - 1) * size, page * size),
    page_info: { page, size, total: items.length },
  };
}

function bucket(status: ConsultantInquiryStatusDto) {
  if (status === "CONSULTATION_REQUIRED" || status === "REOPENED") return "NEW";
  if (status === "RESOLVED" || status === "CANCELLED") return "COMPLETED";
  return "IN_PROGRESS";
}

/**
 * Vite design-mode transport only. It returns synthetic API DTOs to the normal
 * REMOTE UI, never performs network/filesystem I/O, and rejects every mutation.
 * Keep this module out of production entry points and service-worker fallbacks.
 */
export function createDesignPreviewApi() {
  const samples = Array.from({ length: 19 }, (_, index) => createSampleInquiry(index + 1));
  const assigned = samples.filter((sample) => !sample.unassigned);
  const unassigned = samples.filter((sample) => sample.unassigned);
  const statusCounts: ConsultantInquiryListDataDto["status_counts"] = {};
  const summary = { total: assigned.length, new: 0, in_progress: 0, completed: 0 };
  for (const { detail } of assigned) {
    const status = detail.inquiry.status;
    statusCounts[status] = (statusCounts[status] ?? 0) + 1;
    if (bucket(status) === "NEW") summary.new += 1;
    else if (bucket(status) === "COMPLETED") summary.completed += 1;
    else summary.in_progress += 1;
  }
  const fixture = MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA;
  const notices = fixture.notices.map((notice) => ({
    notice_id: notice.noticeId,
    notice_code: notice.noticeCode,
    category_code: notice.categoryCode,
    category: notice.category,
    title: notice.title,
    content: notice.content,
    department: notice.department,
    published_on: notice.publishedOn,
  }));
  const dashboard = {
    data_classification: "synthetic",
    generated_at: "2026-08-31T10:00:00+09:00",
    summary,
    notices,
    consultants: fixture.consultants.map((staff) => ({
      user_id: staff.userId, name: staff.name, department: staff.department,
      position: staff.position, extension: staff.extension, email: staff.email,
    })),
    technicians: fixture.technicians.map((staff) => ({
      user_id: staff.userId, name: staff.name, branch: staff.branch,
      phone: staff.phone, email: staff.email,
    })),
    inquiries: assigned.map(({ detail }) => ({
      inquiry_id: detail.inquiry.inquiry_id,
      inquiry_code: detail.inquiry.inquiry_code,
      bucket: bucket(detail.inquiry.status),
      status: detail.inquiry.status,
      risk_level: detail.inquiry.risk_level,
      priority: detail.inquiry.priority,
      title: detail.symptom_and_questionnaire.symptom_summary,
      detail: detail.symptom_and_questionnaire.symptom_summary,
      contact: detail.customer.phone_masked,
      address: "화면 확인용 합성 주소",
      customer_name: detail.customer.display_name,
      customer_code: `preview-customer-${detail.inquiry.inquiry_code}`,
      product_name: detail.product_and_care!.product_model_name,
      product_code: detail.product_and_care!.product_model,
      warranty_status: "IN_WARRANTY",
      warranty_ends_on: "2027-08-31",
      warranty_label: "무상보증 기간",
      previous_visit_count: detail.visit ? 1 : 0,
      received_at: detail.inquiry.received_at,
      updated_at: detail.inquiry.updated_at,
    })),
  };

  const response = (status: number, data: unknown, code?: string, message?: string): DesignPreviewResponse => ({
    status,
    body: {
      success: status < 400,
      data: status < 400 ? structuredClone(data) : null,
      error: status < 400 ? null : { code: code!, message: message!, details: { preview_only: true } },
      metadata: { correlation_id: "local-design-preview" },
    },
  });

  return (request: DesignPreviewRequest): DesignPreviewResponse => {
    let url: URL;
    try {
      url = new URL(request.url, "http://127.0.0.1");
    } catch {
      return response(400, null, "PREVIEW_INVALID_URL", "로컬 미리보기 요청 주소를 확인해 주세요.");
    }
    const path = url.pathname.replace(/\/$/, "");
    const method = request.method.toUpperCase();

    // The phone search contract uses POST, but this route only reads fixtures.
    if (path === "/api/v1/consultant/customer-subscriptions/search" && method === "POST") {
      const body = request.body && typeof request.body === "object" ? request.body as Record<string, unknown> : {};
      const query = typeof body.query === "string" ? body.query.trim().toLocaleLowerCase() : "";
      const limit = positiveInt(typeof body.limit === "number" ? String(body.limit) : null, 10, 50);
      const items = query ? assigned.flatMap(({ detail }, index) => {
        const product = detail.product_and_care!;
        if (![detail.customer.display_name, detail.customer.phone_masked, product.product_model].join(" ").toLocaleLowerCase().includes(query)) return [];
        return [{
          customer_id: `preview-customer-${index + 1}`,
          customer_display_name: detail.customer.display_name,
          phone_masked: detail.customer.phone_masked,
          subscription_id: `preview-subscription-${index + 1}`,
          subscription_status: "ACTIVE",
          management_type_code: product.management_type,
          product_id: `preview-product-${product.product_model}`,
          product_model_code: product.product_model,
          product_name: product.product_model_name,
        }];
      }).slice(0, limit) : [];
      return response(200, { items, returned_count: items.length });
    }

    if (method !== "GET") {
      return response(405, null, "PREVIEW_READ_ONLY", DESIGN_PREVIEW_READ_ONLY_MESSAGE);
    }
    if (path === "/api/v1/consultant/dashboard") return response(200, dashboard);
    if (path === "/api/v1/inquiries") {
      const data: ConsultantInquiryListDataDto = {
        ...paginate(filteredSamples(assigned, url.searchParams).map(listItem), url.searchParams),
        status_counts: statusCounts,
      };
      return response(200, data);
    }
    if (path === "/api/v1/inquiries/unassigned-consultations") {
      const items: UnassignedConsultationQueueItemDto[] = filteredSamples(unassigned, url.searchParams).map((sample) => ({
        ...listItem(sample),
        status: "CONSULTATION_REQUIRED",
        current_assignee_type: "NONE",
      }));
      const data: UnassignedConsultationQueueDataDto = paginate(items, url.searchParams);
      return response(200, data);
    }
    const inquiryMatch = path.match(/^\/api\/v1\/inquiries\/([^/]+)$/);
    const noticeMatch = path.match(/^\/api\/v1\/consultant\/notices\/([^/]+)$/);
    try {
      if (inquiryMatch) {
        const id = decodeURIComponent(inquiryMatch[1]);
        const sample = samples.find(({ detail }) => detail.inquiry.inquiry_id === id);
        if (sample) return response(200, sample.detail);
      }
      if (noticeMatch) {
        const id = decodeURIComponent(noticeMatch[1]);
        const notice = notices.find((item) => item.notice_id === id);
        if (notice) return response(200, notice);
      }
    } catch {
      return response(400, null, "PREVIEW_INVALID_ID", "로컬 샘플 식별자를 확인해 주세요.");
    }
    return response(404, null, "PREVIEW_NOT_FOUND", "이 요청은 로컬 디자인 미리보기에서 제공하지 않습니다. 운영 서버로 전달되지 않았습니다.");
  };
}
