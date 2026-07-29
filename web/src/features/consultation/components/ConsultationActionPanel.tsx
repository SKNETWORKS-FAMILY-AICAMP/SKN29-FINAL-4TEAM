import type { ChangeEvent } from "react";
import { useState } from "react";

import { useConsultationForm } from "../hooks/useConsultationForm";
import { useSaveConsultation } from "../hooks/useSaveConsultation";
import type {
  CounselorAllowedAction,
  CounselorInquiry,
} from "../model/consultantWorkspaceTypes";
import type { ConsultationMockScenario } from "../model/consultationTypes";

interface ConsultationActionPanelProps {
  inquiry: CounselorInquiry;
  onOpenVisit: (
    entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED",
  ) => void;
}

const MOCK_SCENARIOS: readonly {
  value: ConsultationMockScenario;
  label: string;
}[] = [
  { value: "SUCCESS", label: "성공" },
  { value: "FORBIDDEN", label: "403 권한 없음" },
  { value: "CONFLICT", label: "409 상태 충돌" },
  { value: "VALIDATION_ERROR", label: "422 입력 오류" },
  { value: "NETWORK_ERROR", label: "네트워크 오류" },
];

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <span className="v6-field-error">{message}</span>;
}

function ActionButtons({
  actions,
  disabled,
  onAction,
}: {
  actions: readonly CounselorAllowedAction[];
  disabled: boolean;
  onAction: (action: CounselorAllowedAction) => void;
}) {
  if (actions.length === 0) {
    return (
      <p className="v6-action-note">
        현재 서버 Mock이 허용한 처리 행동이 없습니다.
      </p>
    );
  }

  return (
    <div className="v6-action-buttons">
      {actions.map((action) => (
        <button
          key={action.code}
          className={`v6-button ${
            action.style === "PRIMARY"
              ? "v6-button--primary"
              : "v6-button--secondary"
          } v6-button--full`}
          type="button"
          disabled={disabled}
          onClick={() => onAction(action)}
        >
          {disabled ? "처리 중…" : action.label}
        </button>
      ))}
    </div>
  );
}

export default function ConsultationActionPanel({
  inquiry,
  onOpenVisit,
}: ConsultationActionPanelProps) {
  const [scenario, setScenario] =
    useState<ConsultationMockScenario>("SUCCESS");
  const form = useConsultationForm({
    consultationNote: "",
    additionalCheck: "",
    customerGuidance: "",
    consultationResult: "",
    summaryRevision: inquiry.aiSummaryRevision ?? "",
    summaryConfirmed: Boolean(inquiry.confirmedSummary),
    visitRequired: "UNDECIDED",
    usageStatus: inquiry.usageStatus,
  });
  const save = useSaveConsultation(inquiry);

  const handleAction = async (action: CounselorAllowedAction) => {
    if (!form.validate(action.code)) return;

    const outcome = await save.execute({
      action,
      values: form.values,
      scenario,
    });

    const serverFieldErrors =
      outcome && "error" in outcome ? outcome.error?.fieldErrors : undefined;
    if (serverFieldErrors) {
      form.setServerFieldErrors(serverFieldErrors);
    }

    if (
      outcome &&
      !("error" in outcome) &&
      (action.code === "VISIT_REVIEW_REQUIRED" ||
        action.code === "VISIT_NEEDED")
    ) {
      onOpenVisit(action.code);
    }
  };

  const handleScenarioChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setScenario(event.target.value as ConsultationMockScenario);
  };

  const isConsultationForm = inquiry.status === "CONSULTATION_IN_PROGRESS";

  return (
    <aside
      id="counselor-action-panel"
      className="v6-action-panel"
      aria-label="상담 처리 작업"
    >
      <div className="v6-action-panel__head">
        <small>COUNSEL DESK · MOCK</small>
        <h3>상담 처리</h3>
        <p>
          {inquiry.id} · stateVersion {save.stateVersion}
        </p>
      </div>

      {inquiry.status === "COMPLETION_PENDING" && (
        <>
          <div className="v6-readonly-card">
            <strong>
              {inquiry.feedbackResolved
                ? "고객 해결 피드백이 도착했습니다."
                : "고객 해결 피드백을 기다리고 있습니다."}
            </strong>
            {inquiry.feedbackComment ??
              "고객이 해결 여부를 제출한 뒤 서버가 최종 완료 행동을 허용합니다."}
          </div>
          <ul className="v6-guard-list">
            <li className={inquiry.feedbackResolved ? "" : "is-failed"}>
              해결됨 피드백 저장
            </li>
            <li>상담 경로 문의</li>
            <li>현재 상담원 담당 건</li>
            <li>상담 결과 필수값 완료</li>
          </ul>
        </>
      )}

      {[
        "VISIT_REVIEW_PENDING",
        "VISIT_SCHEDULING",
        "VISIT_SCHEDULED",
        "REVISIT_REQUIRED",
      ].includes(inquiry.status) && (
        <>
          <div className="v6-readonly-card">
            <strong>방문 일정 상태</strong>
            현재 상태와 allowed_actions에 따라 방문 요청 또는 일정 정보를
            확인해 주세요.
          </div>
          <button
            className="v6-button v6-button--secondary v6-button--full v6-visit-link"
            type="button"
            onClick={() => onOpenVisit()}
          >
            방문 전환 정보 확인
          </button>
        </>
      )}

      {inquiry.status === "QUESTIONNAIRE_IN_PROGRESS" && (
        <div className="v6-readonly-card">
          <strong>추가 답변 수집 중</strong>
          현재 서버 Mock이 상담사에게 허용한 처리 행동이 없습니다.
        </div>
      )}

      {isConsultationForm && (
        <form onSubmit={(event) => event.preventDefault()} noValidate>
          <label className="v6-form-field">
            상담 기록 <b>필수</b>
            <textarea
              value={form.values.consultationNote}
              aria-invalid={Boolean(form.fieldErrors.consultationNote)}
              onChange={(event) =>
                form.updateField("consultationNote", event.target.value)
              }
              placeholder="고객에게 추가로 확인한 내용과 안내를 기록하세요."
            />
            <FieldError message={form.fieldErrors.consultationNote} />
          </label>
          <label className="v6-form-field">
            추가 확인사항
            <textarea
              value={form.values.additionalCheck}
              onChange={(event) =>
                form.updateField("additionalCheck", event.target.value)
              }
              placeholder="추가 문진이나 확인이 필요한 내용을 입력하세요."
            />
          </label>
          <label className="v6-form-field">
            고객 안내 <b>완료 시 필수</b>
            <textarea
              value={form.values.customerGuidance}
              aria-invalid={Boolean(form.fieldErrors.customerGuidance)}
              onChange={(event) =>
                form.updateField("customerGuidance", event.target.value)
              }
              placeholder="고객에게 실제로 안내한 내용을 입력하세요."
            />
            <FieldError message={form.fieldErrors.customerGuidance} />
          </label>
          <label className="v6-form-field">
            상담 결과 <b>완료 시 필수</b>
            <textarea
              value={form.values.consultationResult}
              aria-invalid={Boolean(form.fieldErrors.consultationResult)}
              onChange={(event) =>
                form.updateField("consultationResult", event.target.value)
              }
              placeholder="상담 처리 결과를 입력하세요."
            />
            <FieldError message={form.fieldErrors.consultationResult} />
          </label>
          <label className="v6-form-field">
            상담사 수정 요약
            <textarea
              value={form.values.summaryRevision}
              aria-invalid={Boolean(form.fieldErrors.summaryRevision)}
              onChange={(event) =>
                form.updateField("summaryRevision", event.target.value)
              }
              placeholder="AI 초안을 검토한 상담사 수정본을 입력하세요."
            />
            <FieldError message={form.fieldErrors.summaryRevision} />
          </label>
          <label className="v6-check-field">
            <input
              type="checkbox"
              checked={form.values.summaryConfirmed}
              onChange={(event) =>
                form.updateField("summaryConfirmed", event.target.checked)
              }
            />
            상담사가 요약 내용을 검토하고 확정했습니다.
          </label>
          <FieldError message={form.fieldErrors.summaryConfirmed} />
          <label className="v6-form-field">
            방문 필요 여부 <b>완료 시 필수</b>
            <select
              value={form.values.visitRequired}
              aria-invalid={Boolean(form.fieldErrors.visitRequired)}
              onChange={(event) =>
                form.updateField(
                  "visitRequired",
                  event.target.value as typeof form.values.visitRequired,
                )
              }
            >
              <option value="UNDECIDED">선택해 주세요</option>
              <option value="REQUIRED">방문 필요</option>
              <option value="NOT_REQUIRED">방문 불필요</option>
            </select>
            <FieldError message={form.fieldErrors.visitRequired} />
          </label>
          <label className="v6-form-field">
            처리 후 사용 안내
            <select
              value={form.values.usageStatus}
              onChange={(event) =>
                form.updateField(
                  "usageStatus",
                  event.target.value as typeof form.values.usageStatus,
                )
              }
            >
              <option value="NORMAL">일반 사용 가능</option>
              <option value="PARTIAL_STOP">일부 출수·기능 사용 중지</option>
              <option value="TOTAL_STOP">제품 전체 사용 중지</option>
              <option value="PENDING_CONSULTATION">
                상담 확인 전 안내 보류
              </option>
            </select>
          </label>
        </form>
      )}

      {save.allowedActions.length > 0 && (
        <label className="v6-form-field v6-mock-selector">
          Mock 응답 테스트
          <select value={scenario} onChange={handleScenarioChange}>
            {MOCK_SCENARIOS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <small>실제 API가 연결되면 제거되는 개발용 선택 항목입니다.</small>
        </label>
      )}

      {inquiry.status !== "QUESTIONNAIRE_IN_PROGRESS" && (
        <ActionButtons
          actions={save.allowedActions}
          disabled={save.isSaving}
          onAction={handleAction}
        />
      )}

      {save.success && (
        <p className="v6-action-message is-success" role="status">
          {save.success.message}
          <small>
            stateVersion {save.success.stateVersion} · correlation_id {" "}
            {save.success.correlationId.slice(0, 8)}…
          </small>
        </p>
      )}
      {save.error && (
        <p
          className={`v6-action-message is-${save.error.kind.toLowerCase()}`}
          role="alert"
        >
          {save.error.message}
          {save.error.kind === "CONFLICT" && (
            <small>
              최신 stateVersion {save.error.currentStateVersion} 반영 · 자동
              재시도 안 함
            </small>
          )}
        </p>
      )}
    </aside>
  );
}
