import PriorityBadge from "../../../common/components/badge/PriorityBadge";
import RiskBadge from "../../../common/components/badge/RiskBadge";
import StatusBadge from "../../../common/components/badge/StatusBadge";
import EvidenceCard from "../../evidence-viewer/components/EvidenceCard";
import { mapEvidenceToCard } from "../../evidence-viewer/model/evidenceMapper";
import {
  formatWorkspaceDateTime,
  getPriorityVariant,
  getStatusBadgeVariant,
  PRIORITY_LABELS,
  STATUS_LABELS,
} from "../model/consultantWorkspaceModel";
import type {
  CounselorInquiry,
  DetailTab,
} from "../model/consultantWorkspaceTypes";
import ConsultationActionPanel from "./ConsultationActionPanel";
import WorkspaceChip from "./WorkspaceChip";

interface ConsultantInquiryDetailProps {
  detailTab: DetailTab;
  inquiry: CounselorInquiry | null;
  onDetailTabChange: (tab: DetailTab) => void;
  onOpenVisit: (
    entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED",
  ) => void;
  sectionStates?: ConsultantDetailSectionStates;
}

export interface ConsultantDetailSectionStates {
  aiSummary: "ready" | "error";
  evidence: "ready" | "error";
  timeline: "ready" | "error";
}

const READY_SECTIONS: ConsultantDetailSectionStates = {
  aiSummary: "ready",
  evidence: "ready",
  timeline: "ready",
};

const DETAIL_TABS: readonly { id: DetailTab; label: string }[] = [
  { id: "summary", label: "통합 요약" },
  { id: "answers", label: "고객 답변" },
  { id: "evidence", label: "공식 근거·사용 상태" },
  { id: "timeline", label: "처리 이력" },
];

function UsageSection({ inquiry }: { inquiry: CounselorInquiry }) {
  const isDanger = inquiry.usageStatus !== "NORMAL";
  const usageLabel =
    inquiry.usageStatus === "TOTAL_STOP"
      ? "제품 전체 사용 중지"
      : inquiry.usageStatus === "PARTIAL_STOP"
        ? "일부 출수·기능 사용 중지"
        : inquiry.usageStatus === "PENDING_CONSULTATION"
          ? "상담 확인 전 안내 보류"
          : "일반 사용 가능";

  return (
    <section className="v6-section">
      <div className="v6-section__head">
        <h3>현재 사용 안내 상태</h3>
        <div className="v6-chip-row">
          <WorkspaceChip
            label={usageLabel}
            tone={isDanger ? "danger" : "success"}
          />
          <WorkspaceChip label={inquiry.assignedCounselor} />
        </div>
      </div>

      <div className={`v6-usage-card${isDanger ? " is-danger" : ""}`}>
        <span>{isDanger ? "!" : "✓"}</span>
        <div>
          <strong>{usageLabel}</strong>
          <p>{inquiry.usageMessage}</p>
          <dl>
            <div>
              <dt>제한 출수</dt>
              <dd>{inquiry.restrictedWaterTypes.join(" · ") || "없음"}</dd>
            </div>
            <div>
              <dt>제한 기능</dt>
              <dd>{inquiry.restrictedFunctions.join(" · ") || "없음"}</dd>
            </div>
            <div>
              <dt>판단 근거</dt>
              <dd>{inquiry.guidanceBasis}</dd>
            </div>
            <div>
              <dt>다음 행동</dt>
              <dd>{inquiry.nextAction}</dd>
            </div>
            <div>
              <dt>갱신 시각</dt>
              <dd>{formatWorkspaceDateTime(inquiry.updatedAt)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

function CustomerProductSection({ inquiry }: { inquiry: CounselorInquiry }) {
  const rows = [
    ["고객·구독", `${inquiry.customerId} · ${inquiry.subscriptionId}`],
    ["제품·매뉴얼", `${inquiry.productCode} · ${inquiry.manualModel}`],
    ["문의·시나리오", `${inquiry.inquiryCode} · ${inquiry.scenarioId}`],
    ["문의 공개 ID", inquiry.inquiryId],
    ["담당 상담원", inquiry.assignedCounselor],
    [
      "관리 유형·사용 시작일",
      `${inquiry.managementType} · ${formatWorkspaceDateTime(inquiry.serviceStartDate)}`,
    ],
    ["최근 관리일", formatWorkspaceDateTime(inquiry.lastCareDate)],
    ["최근 필터·카트리지 교체일", formatWorkspaceDateTime(inquiry.lastFilterDate)],
    ["다음 케어 예정·기준", `${inquiry.nextCareDate} · ${inquiry.nextCareBasis}`],
  ];

  return (
    <section className="v6-section">
      <div className="v6-section__head">
        <h3>고객·제품·관리 이력</h3>
        <span>고객 재입력 없음</span>
      </div>
      <dl className="v6-summary-grid">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function AnswersSection({ inquiry }: { inquiry: CounselorInquiry }) {
  return (
    <>
      <section className="v6-section">
        <div className="v6-section__head">
          <h3>고객 최초 입력</h3>
          <span>원문 보존</span>
        </div>
        <blockquote className="v6-original">
          “{inquiry.customerMessage}”
        </blockquote>
      </section>

      <section className="v6-section">
        <div className="v6-section__head">
          <h3>구조화된 고객 답변</h3>
          <span>반복 질문 방지</span>
        </div>
        <dl className="v6-answer-grid">
          <div>
            <dt>발생 조건</dt>
            <dd>{inquiry.conditions}</dd>
          </div>
          <div>
            <dt>표시 문구·오류</dt>
            <dd>{inquiry.displayCode}</dd>
          </div>
        </dl>
      </section>

      <section className="v6-section">
        <div className="v6-section__head">
          <h3>고객 수행 조치·결과</h3>
          <span>상담·기사 인계</span>
        </div>
        <dl className="v6-answer-grid">
          <div>
            <dt>수행한 조치</dt>
            <dd>{inquiry.performedAction}</dd>
          </div>
          <div>
            <dt>조치 결과</dt>
            <dd>{inquiry.actionResult}</dd>
          </div>
        </dl>
      </section>
    </>
  );
}

function EvidenceSection({
  inquiry,
  status,
}: {
  inquiry: CounselorInquiry;
  status: ConsultantDetailSectionStates["evidence"];
}) {
  return (
    <section className="v6-section">
      <div className="v6-section__head">
        <h3>EvidenceCardDTO · 공식 근거</h3>
        <span>{inquiry.evidence.length}건</span>
      </div>

      {status === "error" ? (
        <div className="v6-error" role="alert">
          <strong>공식 근거를 불러오지 못했습니다.</strong>
          <p>근거 확인 전에는 AI 초안을 공식 안내처럼 사용하지 마세요. 다른 상세 정보는 계속 확인할 수 있습니다.</p>
        </div>
      ) : inquiry.evidence.length === 0 ? (
        <div className="v6-evidence-hold">
          연결된 공식 근거가 없습니다. 임의 안내를 생성하지 말고 상담
          검토를 계속하세요.
        </div>
      ) : (
        <div className="v6-evidence-list">
          {inquiry.evidence.map((item) => (
            <EvidenceCard
              key={`${item.documentTitle}-${item.page}`}
              evidence={mapEvidenceToCard(item)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function AiSummarySection({
  inquiry,
  status,
}: {
  inquiry: CounselorInquiry;
  status: ConsultantDetailSectionStates["aiSummary"];
}) {
  if (status === "error") {
    return (
      <section className="v6-section">
        <div className="v6-section__head">
          <h3>AI 상담 요약·상담사 확정본</h3>
        </div>
        <div className="v6-error" role="alert">
          <strong>AI 상담 요약을 불러오지 못했습니다.</strong>
          <p>고객 원문과 문진 답변, 공식 근거를 직접 확인해 주세요.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="v6-section">
      <div className="v6-section__head">
        <h3>AI 상담 요약·상담사 확정본</h3>
        <div className="v6-chip-row">
          <WorkspaceChip
            label={inquiry.aiStatus}
            tone={inquiry.aiStatus === "FAILED" ? "danger" : "success"}
          />
          <WorkspaceChip label={inquiry.aiOutcome} tone="danger" />
        </div>
      </div>

      <div className="v6-ai-summary">
        <span>AI</span>
        <div>
          <strong>AI 상담 요약 초안 · 수정 불가</strong>
          <p>{inquiry.aiSummaryOriginal}</p>
        </div>
      </div>

      <div className="v6-readonly-card">
        <strong>
          {inquiry.aiSummaryRevision
            ? "상담사 수정본"
            : "상담사 수정본 없음"}
        </strong>
        {inquiry.aiSummaryRevision ??
          "AI 초안을 그대로 승인하거나 필요한 보완 내용을 별도 수정본으로 저장합니다."}
      </div>
      <div className="v6-readonly-card">
        <strong>
          {inquiry.confirmedSummary
            ? "상담사 확정본"
            : "상담사 확정본 없음"}
        </strong>
        {inquiry.confirmedSummary ?? "방문 인계 전 상담 요약을 확정해 주세요."}
      </div>
    </section>
  );
}

function TimelineSection({
  inquiry,
  status,
}: {
  inquiry: CounselorInquiry;
  status: ConsultantDetailSectionStates["timeline"];
}) {
  return (
    <section className="v6-section">
      <div className="v6-section__head">
        <h3>문의 처리 이력</h3>
        <span>{inquiry.timeline.length}건</span>
      </div>
      {status === "error" ? (
        <div className="v6-error" role="alert">
          <strong>처리 이력을 불러오지 못했습니다.</strong>
          <p>상세 정보와 상담 입력은 계속 확인할 수 있습니다.</p>
        </div>
      ) : <ol className="v6-timeline">
        {inquiry.timeline.map((item) => (
          <li key={`${item.title}-${item.occurredAt}`}>
            <i />
            <div>
              <header>
                <strong>{item.title}</strong>
                <time>{item.occurredAt}</time>
              </header>
              <p>
                {item.description} · {item.actor}
              </p>
            </div>
          </li>
        ))}
      </ol>}
    </section>
  );
}

export default function ConsultantInquiryDetail({
  detailTab,
  inquiry,
  onDetailTabChange,
  onOpenVisit,
  sectionStates = READY_SECTIONS,
}: ConsultantInquiryDetailProps) {
  if (!inquiry) {
    return (
      <section className="v6-detail">
        <div className="v6-detail-empty">
          <span>▤</span>
          <strong>확인할 문의를 선택해 주세요.</strong>
          <p>왼쪽 우선순위 큐에서 문의를 선택하면 상세가 표시됩니다.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="v6-detail" id="counselor-detail">
      <article>
        <header className="v6-detail-head">
          <div>
            <div className="v6-chip-row">
              <WorkspaceChip label="합성 시연" tone="info" />
              <StatusBadge
                label={STATUS_LABELS[inquiry.status]}
                size="compact"
                variant={getStatusBadgeVariant(inquiry.status)}
              />
              <RiskBadge
                level={inquiry.riskLevel.toLowerCase()}
                size="compact"
              />
              <PriorityBadge
                label={PRIORITY_LABELS[inquiry.priority]}
                size="compact"
                variant={getPriorityVariant(inquiry.priority)}
              />
              {inquiry.requiresConsultation && (
                <WorkspaceChip label="상담 필수" tone="danger" />
              )}
            </div>
            <h2>{inquiry.symptomLabel}</h2>
            <p>
              {inquiry.inquiryCode} · {inquiry.scenarioId} · 접수{" "}
              {formatWorkspaceDateTime(inquiry.createdAt)}
            </p>
          </div>

          <div className="v6-customer-card">
            <span>{inquiry.customerName.slice(-3)}</span>
            <div>
              <strong>{inquiry.customerName}</strong>
              <small>
                {inquiry.customerId} · {inquiry.productCode}
              </small>
            </div>
          </div>
        </header>

        <nav className="v6-tabs" aria-label="문의 상세 탭" role="tablist">
          {DETAIL_TABS.map((tab) => (
            <button
              key={tab.id}
              className={detailTab === tab.id ? "is-active" : ""}
              type="button"
              role="tab"
              aria-selected={detailTab === tab.id}
              onClick={() => onDetailTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="v6-detail-body">
          <div className="v6-detail-content">
            {inquiry.riskLevel === "DANGER" && (
              <div className="v6-danger-alert">
                <b>!</b>
                <div>
                  <strong>사용·음용 중지 우선 문의</strong>
                  <p>
                    위험 신호와 안전조치 이행 여부를 먼저 확인하고, 일반
                    자가조치를 안내하지 마세요.
                  </p>
                </div>
              </div>
            )}

            {detailTab === "summary" && (
              <>
                <UsageSection inquiry={inquiry} />
                <CustomerProductSection inquiry={inquiry} />
                <AnswersSection inquiry={inquiry} />
                <EvidenceSection
                  inquiry={inquiry}
                  status={sectionStates.evidence}
                />
                <AiSummarySection
                  inquiry={inquiry}
                  status={sectionStates.aiSummary}
                />
                {inquiry.feedbackResolved && (
                  <section className="v6-section">
                    <div className="v6-section__head">
                      <h3>고객 해결 피드백</h3>
                      <WorkspaceChip label="해결됨" tone="success" />
                    </div>
                    <dl className="v6-summary-grid">
                      <div>
                        <dt>고객 의견</dt>
                        <dd>{inquiry.feedbackComment}</dd>
                      </div>
                      <div>
                        <dt>제출 시각</dt>
                        <dd>{formatWorkspaceDateTime(inquiry.updatedAt)}</dd>
                      </div>
                    </dl>
                  </section>
                )}
              </>
            )}
            {detailTab === "answers" && <AnswersSection inquiry={inquiry} />}
            {detailTab === "evidence" && (
              <>
                <UsageSection inquiry={inquiry} />
                <EvidenceSection
                  inquiry={inquiry}
                  status={sectionStates.evidence}
                />
                <AiSummarySection
                  inquiry={inquiry}
                  status={sectionStates.aiSummary}
                />
              </>
            )}
            {detailTab === "timeline" && (
              <TimelineSection
                inquiry={inquiry}
                status={sectionStates.timeline}
              />
            )}
          </div>

          <ConsultationActionPanel
            key={inquiry.inquiryId}
            inquiry={inquiry}
            onOpenVisit={onOpenVisit}
          />
        </div>
      </article>
    </section>
  );
}
