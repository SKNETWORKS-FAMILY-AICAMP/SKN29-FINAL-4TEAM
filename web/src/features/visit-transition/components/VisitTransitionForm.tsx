import { useState } from "react";

import type { CounselorInquiry } from "../../consultation/model/consultantWorkspaceTypes";
import {
  createVisitTransitionMockValues,
  MOCK_TECHNICIANS,
} from "../model/visitTransitionMock";
import type {
  VisitMockAction,
  VisitTransitionErrors,
  VisitTransitionField,
  VisitTransitionValues,
} from "../model/visitTransitionTypes";
import { validateVisitTransition } from "../validation/visitTransitionSchema";

interface VisitTransitionFormProps {
  availableActions?: readonly VisitMockAction[];
  inquiry: CounselorInquiry;
  stateVersion: number;
  symptomSummary: string;
  onMockSaved: (nextVersion: number, action: VisitMockAction) => void;
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <span className="visit-v13-field-error">{message}</span>;
}

export default function VisitTransitionForm({
  availableActions = ["SAVE_SCHEDULE", "CONFIRM_VISIT"],
  inquiry,
  stateVersion,
  symptomSummary,
  onMockSaved,
}: VisitTransitionFormProps) {
  const canSaveSchedule = availableActions.includes("SAVE_SCHEDULE");
  const canConfirmVisit = availableActions.includes("CONFIRM_VISIT");
  const canCreateVisitRequest = availableActions.includes(
    "CREATE_VISIT_REQUEST",
  );
  const [values, setValues] = useState<VisitTransitionValues>(() =>
    createVisitTransitionMockValues(symptomSummary),
  );
  const [errors, setErrors] = useState<VisitTransitionErrors>({});
  const [successAction, setSuccessAction] = useState<VisitMockAction | null>(
    null,
  );

  const updateField = (
    field: VisitTransitionField,
    value: VisitTransitionValues[VisitTransitionField],
  ) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => {
      if (!(field in current)) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
    setSuccessAction(null);
  };

  const submitMock = (action: VisitMockAction) => {
    const nextErrors = validateVisitTransition(values, action);
    setErrors(nextErrors);
    setSuccessAction(null);
    if (Object.keys(nextErrors).length > 0) return;

    setSuccessAction(action);
    onMockSaved(stateVersion + 1, action);
  };

  const selectedTechnician = MOCK_TECHNICIANS.find(
    (item) => item.id === values.technicianId,
  );

  return (
    <div className="visit-v13-layout">
      <aside className="visit-v13-context" aria-label="방문 전환 문의 요약">
        <header>
          <small>HANDOFF CONTEXT</small>
          <h2>기사 인계 기준</h2>
          <p>상담에서 확인된 정보만 전달하며 현장 진단을 임의로 추가하지 않습니다.</p>
        </header>

        <section className="visit-v13-danger-card">
          <span aria-hidden="true">!</span>
          <div>
            <strong>{inquiry.symptomLabel}</strong>
            <p>{symptomSummary}</p>
          </div>
        </section>

        <dl className="visit-v13-summary-list">
          <div>
            <dt>문의·시나리오</dt>
            <dd>{inquiry.inquiryCode}</dd>
            <dd>{inquiry.scenarioId}</dd>
          </div>
          <div>
            <dt>고객·제품</dt>
            <dd>{inquiry.customerName}</dd>
            <dd>{inquiry.productCode}</dd>
          </div>
          <div>
            <dt>사용 안내</dt>
            <dd>{inquiry.usageMessage}</dd>
          </div>
          <div>
            <dt>담당 상담원</dt>
            <dd>{inquiry.assignedCounselor}</dd>
          </div>
        </dl>

        <ol className="visit-v13-steps" aria-label="방문 전환 단계">
          <li className="is-complete"><b>1</b><span>상담 정보 확인</span></li>
          <li className="is-current"><b>2</b><span>기사·희망일 입력</span></li>
          <li><b>3</b><span>가상 일정 확정</span></li>
        </ol>
      </aside>

      <section className="visit-v13-form-panel">
        <header className="visit-v13-form-head">
          <div>
            <small>VISIT TRANSITION · MOCK</small>
            <h2>방문 전환 정보</h2>
            <p>입력과 검증만 동작하며 실제 기사 배정·일정 저장은 하지 않습니다.</p>
          </div>
          <span>stateVersion {stateVersion}</span>
        </header>

        <div className="visit-v13-status-card">
          <div>
            <small>방문 일정 상태</small>
            <strong>
              {successAction === "CONFIRM_VISIT"
                ? "방문 확정 · Mock"
                : successAction === "CREATE_VISIT_REQUEST"
                  ? "방문 요청 생성 · Mock"
                  : canCreateVisitRequest
                    ? "방문 필요 검토 · Mock"
                    : "일정 조율 중 · Mock"}
            </strong>
          </div>
          <div>
            <small>선택 기사</small>
            <strong>{selectedTechnician?.name ?? "미배정"}</strong>
          </div>
          <div>
            <small>고객 희망일</small>
            <strong>{values.preferredDate || "미입력"}</strong>
          </div>
        </div>

        <form
          className="visit-v13-form"
          onSubmit={(event) => event.preventDefault()}
          noValidate
        >
          <label className="visit-v13-field is-wide">
            <span>방문 사유 <b>필수</b></span>
            <textarea
              value={values.visitReason}
              aria-invalid={Boolean(errors.visitReason)}
              onChange={(event) => updateField("visitReason", event.target.value)}
              placeholder="방문 전환이 필요한 이유를 기록하세요."
            />
            <FieldError message={errors.visitReason} />
          </label>

          <label className="visit-v13-field">
            <span>고객 희망일 <b>필수</b></span>
            <input
              type="date"
              aria-label="고객 희망일"
              value={values.preferredDate}
              aria-invalid={Boolean(errors.preferredDate)}
              onChange={(event) =>
                updateField("preferredDate", event.target.value)
              }
            />
            <FieldError message={errors.preferredDate} />
          </label>

          <label className="visit-v13-field">
            <span>가상 방문기사 <b>필수</b></span>
            <select
              value={values.technicianId}
              aria-invalid={Boolean(errors.technicianId)}
              onChange={(event) => updateField("technicianId", event.target.value)}
            >
              <option value="">기사를 선택하세요</option>
              {MOCK_TECHNICIANS.map((technician) => (
                <option key={technician.id} value={technician.id}>
                  {technician.name} · {technician.team}
                </option>
              ))}
            </select>
            {selectedTechnician && (
              <small className="visit-v13-field-hint">
                담당 권역 · {selectedTechnician.area}
              </small>
            )}
            <FieldError message={errors.technicianId} />
          </label>

          <label className="visit-v13-field is-wide">
            <span>점검 우선순위 <b>필수</b></span>
            <textarea
              value={values.inspectionPriority}
              aria-invalid={Boolean(errors.inspectionPriority)}
              onChange={(event) =>
                updateField("inspectionPriority", event.target.value)
              }
              placeholder="위험도와 상담 결과를 기준으로 우선 점검 항목을 기록하세요."
            />
            <FieldError message={errors.inspectionPriority} />
          </label>

          <label className="visit-v13-field">
            <span>기사 전달사항 <b>필수</b></span>
            <textarea
              value={values.notes}
              aria-invalid={Boolean(errors.notes)}
              onChange={(event) => updateField("notes", event.target.value)}
              placeholder="고객 답변과 현장 인계 사항을 기록하세요."
            />
            <FieldError message={errors.notes} />
          </label>

          <label className="visit-v13-field">
            <span>안전 유의사항 <b>필수</b></span>
            <textarea
              value={values.safetyNotes}
              aria-invalid={Boolean(errors.safetyNotes)}
              onChange={(event) => updateField("safetyNotes", event.target.value)}
              placeholder="현장에서 재확인할 안전 항목을 기록하세요."
            />
            <FieldError message={errors.safetyNotes} />
          </label>

          <label className="visit-v13-field is-wide">
            <span>가상 방문 확정일 <em>방문 확정 시 필수</em></span>
            <input
              type="date"
              aria-label="가상 방문 확정일"
              value={values.confirmedDate}
              aria-invalid={Boolean(errors.confirmedDate)}
              onChange={(event) =>
                updateField("confirmedDate", event.target.value)
              }
            />
            <small className="visit-v13-field-hint">
              고객 희망일과 실제 확정일을 구분해 입력합니다.
            </small>
            <FieldError message={errors.confirmedDate} />
          </label>
        </form>

        <div className="visit-v13-actions">
          {canCreateVisitRequest && (
            <button
              className="is-primary"
              type="button"
              onClick={() => submitMock("CREATE_VISIT_REQUEST")}
            >
              방문 필요 확정·요청 생성
            </button>
          )}
          {canSaveSchedule && (
            <button type="button" onClick={() => submitMock("SAVE_SCHEDULE")}>
              일정 조율 저장
            </button>
          )}
          {canConfirmVisit && (
            <button
              className="is-primary"
              type="button"
              onClick={() => submitMock("CONFIRM_VISIT")}
            >
              방문 확정
            </button>
          )}
        </div>

        {Object.keys(errors).length > 0 && (
          <p className="visit-v13-message is-error" role="alert">
            필수 입력을 확인해 주세요. 작성한 내용은 그대로 유지됩니다.
          </p>
        )}

        {successAction && (
          <div className="visit-v13-success" role="status">
            <span aria-hidden="true">✓</span>
            <div>
              <strong>
                {successAction === "CONFIRM_VISIT"
                  ? "Mock 방문 일정이 확정되었습니다."
                  : successAction === "CREATE_VISIT_REQUEST"
                    ? "Mock 방문 요청을 생성하고 일정 조율 단계로 전환했습니다."
                    : "Mock 일정 조율 내용을 저장했습니다."}
              </strong>
              <p>
                실제 기사 배정·알림·일정 생성은 수행하지 않았습니다. 화면 시연용
                결과입니다.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
