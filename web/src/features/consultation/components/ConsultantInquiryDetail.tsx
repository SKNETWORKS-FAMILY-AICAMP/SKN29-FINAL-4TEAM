import { useState } from "react";

import {
  formatWorkspaceDateTime,
  getRiskTone,
  getStatusTone,
  RISK_LABELS,
  STATUS_LABELS,
} from "../model/consultantWorkspaceModel";
import type {
  CounselorInquiry,
  DetailTab,
} from "../model/consultantWorkspaceTypes";
import WorkspaceChip from "./WorkspaceChip";

interface ConsultantInquiryDetailProps {
  detailTab: DetailTab;
  inquiry: CounselorInquiry | null;
  onDetailTabChange: (tab: DetailTab) => void;
  onOpenVisit: () => void;
}

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
    ["문의·시나리오", `${inquiry.id} · ${inquiry.scenarioId}`],
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

function EvidenceSection({ inquiry }: { inquiry: CounselorInquiry }) {
  return (
    <section className="v6-section">
      <div className="v6-section__head">
        <h3>EvidenceCardDTO · 공식 근거</h3>
        <span>{inquiry.evidence.length}건</span>
      </div>

      {inquiry.evidence.length === 0 ? (
        <div className="v6-evidence-hold">
          연결된 공식 근거가 없습니다. 임의 안내를 생성하지 말고 상담
          검토를 계속하세요.
        </div>
      ) : (
        <div className="v6-evidence-list">
          {inquiry.evidence.map((item) => {
            const metadata = [
              ["evidence_id", item.evidenceId],
              ["chunk_id", item.chunkId],
              ["document_id", item.documentId],
              ["문서 버전", item.documentVersion],
              ["근거 페이지", `${item.page}쪽`],
              ["근거 항목", item.sectionTitle],
              ["출처 유형", "official_manual"],
              ["제공기관", "SK매직"],
              ["위험도", item.riskLevel],
              ["상담 필수", "예"],
              ["안전 조치", item.safeActions.join(" · ")],
              ["금지 행동", item.prohibitedActions.join(" · ")],
              ["검증 상태", "text_and_visual_verified"],
              ["상품 코드", inquiry.productCode],
              ["매뉴얼 모델", inquiry.manualModel],
              ["제품 세대", "D"],
              ["모델 계열", "WPU-JAC104"],
              ["적용 범위", "mvp_primary"],
              ["데이터 분류", "official"],
            ];

            return (
              <article key={item.evidenceId} className="v6-evidence-card">
                <span className="v6-evidence-card__icon">
                  공식
                  <br />
                  매뉴얼
                </span>
                <div>
                  <div className="v6-chip-row">
                    <WorkspaceChip
                      label="텍스트·시각 검증 완료"
                      tone="success"
                    />
                    <WorkspaceChip label="mvp_primary" tone="info" />
                  </div>
                  <h4>{item.documentTitle}</h4>
                  <p>{item.summary}</p>
                  <div className="v6-evidence-meta">
                    {metadata.map(([label, value]) => (
                      <span key={label}>
                        {label} · {value}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="v6-evidence-actions">
                  <a
                    href={item.sourceLandingUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    공식 출처 보기 ↗
                  </a>
                  <a
                    href={item.sourceDirectDownloadUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    설명서 PDF 열기 ↗
                  </a>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function AiSummarySection({ inquiry }: { inquiry: CounselorInquiry }) {
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

function TimelineSection({ inquiry }: { inquiry: CounselorInquiry }) {
  return (
    <section className="v6-section">
      <div className="v6-section__head">
        <h3>문의 처리 이력</h3>
        <span>{inquiry.timeline.length}건</span>
      </div>
      <ol className="v6-timeline">
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
      </ol>
    </section>
  );
}

function ActionPanel({
  inquiry,
  onOpenVisit,
}: {
  inquiry: CounselorInquiry;
  onOpenVisit: () => void;
}) {
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState("");
  const [message, setMessage] = useState("");

  const submit = () => {
    if (!note.trim()) {
      setMessage("상담 기록을 입력해 주세요.");
      return;
    }
    setMessage(
      "Mock 상담 기록을 저장했습니다. 실제 API에는 전송되지 않습니다.",
    );
  };

  return (
    <aside
      id="counselor-action-panel"
      className="v6-action-panel"
      aria-label="상담 처리 작업"
    >
      <div className="v6-action-panel__head">
        <small>COUNSEL DESK</small>
        <h3>상담 처리</h3>
        <p>
          {inquiry.id} · stateVersion {inquiry.stateVersion}
        </p>
      </div>

      {inquiry.status === "COMPLETION_PENDING" ? (
        <>
          <div className="v6-readonly-card">
            <strong>
              {inquiry.feedbackResolved
                ? "고객 해결 피드백이 도착했습니다."
                : "고객 해결 피드백을 기다리고 있습니다."}
            </strong>
            {inquiry.feedbackComment ??
              "상담 결과를 확인한 고객이 해결 여부를 제출하면 최종 완료할 수 있습니다."}
          </div>
          <ul className="v6-guard-list">
            <li className={inquiry.feedbackResolved ? "" : "is-failed"}>
              해결됨 피드백 저장
            </li>
            <li>상담 경로 문의</li>
            <li>현재 상담원 담당 건</li>
            <li>상담 결과 필수값 완료</li>
          </ul>
          <div className="v6-action-buttons">
            <button
              className="v6-button v6-button--primary v6-button--full"
              type="button"
              disabled
            >
              문의 최종 완료
            </button>
          </div>
        </>
      ) : inquiry.status === "VISIT_SCHEDULED" ? (
        <>
          <div className="v6-readonly-card">
            <strong>방문 일정 상태</strong>
            방문 예정 · 기사 배정과 확정 일정을 확인해 주세요.
          </div>
          <div className="v6-action-buttons">
            <button
              className="v6-button v6-button--primary v6-button--full"
              type="button"
              onClick={onOpenVisit}
            >
              방문 전환 정보 확인
            </button>
          </div>
        </>
      ) : inquiry.status === "CONSULTATION_REQUIRED" ? (
        <div className="v6-action-buttons">
          <button
            className="v6-button v6-button--primary v6-button--full"
            type="button"
            onClick={() => setMessage("Mock 상담을 시작했습니다.")}
          >
            상담 시작
          </button>
        </div>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <label className="v6-form-field">
            상담 기록
            <textarea
              required
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="고객에게 추가로 확인한 내용과 안내를 기록하세요."
            />
          </label>
          <label className="v6-form-field">
            상담 결과
            <textarea
              value={outcome}
              onChange={(event) => setOutcome(event.target.value)}
              placeholder="상담 완료 시 처리 결과를 입력하세요."
            />
          </label>
          <label className="v6-form-field">
            처리 후 사용 안내
            <select defaultValue={inquiry.usageStatus}>
              <option value="NORMAL">일반 사용 가능</option>
              <option value="PARTIAL_STOP">일부 출수·기능 사용 중지</option>
              <option value="TOTAL_STOP">제품 전체 사용 중지</option>
            </select>
          </label>
          <div className="v6-action-buttons">
            <button
              className="v6-button v6-button--secondary v6-button--full"
              type="button"
              onClick={onOpenVisit}
            >
              방문 필요 검토
            </button>
            <button
              className="v6-button v6-button--primary v6-button--full"
              type="submit"
            >
              방문 불필요 · 상담 완료
            </button>
          </div>
        </form>
      )}

      {message && <p className="v6-action-note">{message}</p>}
    </aside>
  );
}

export default function ConsultantInquiryDetail({
  detailTab,
  inquiry,
  onDetailTabChange,
  onOpenVisit,
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
              <WorkspaceChip
                label={STATUS_LABELS[inquiry.status]}
                tone={getStatusTone(inquiry.status)}
              />
              <WorkspaceChip
                label={RISK_LABELS[inquiry.riskLevel]}
                tone={getRiskTone(inquiry.riskLevel)}
              />
              {inquiry.requiresConsultation && (
                <WorkspaceChip label="상담 필수" tone="danger" />
              )}
            </div>
            <h2>{inquiry.symptomLabel}</h2>
            <p>
              {inquiry.id} · {inquiry.scenarioId} · 접수{" "}
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
                <EvidenceSection inquiry={inquiry} />
                <AiSummarySection inquiry={inquiry} />
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
                <EvidenceSection inquiry={inquiry} />
                <AiSummarySection inquiry={inquiry} />
              </>
            )}
            {detailTab === "timeline" && (
              <TimelineSection inquiry={inquiry} />
            )}
          </div>

          <ActionPanel inquiry={inquiry} onOpenVisit={onOpenVisit} />
        </div>
      </article>
    </section>
  );
}
