import { useState } from "react";

import type {
  CounselorAllowedAction,
  CounselorInquiry,
  CounselorStatus,
} from "../../consultation/model/consultantWorkspaceTypes";
import { consultantWorkspaceRepository } from "../../consultation/repositories/consultantWorkspaceRepository";
import { MOCK_TECHNICIANS } from "../model/visitTransitionMock";

interface InlineVisitSchedulerProps {
  inquiry: CounselorInquiry;
  stateVersion: number;
  initialDesiredAt?: string;
  onBack: () => void;
  onStateChange: (update: {
    status: CounselorStatus;
    stateVersion: number;
    allowedActions: readonly CounselorAllowedAction[];
  }) => void;
}

interface ScheduleErrors {
  confirmedAt?: string;
  desiredAt?: string;
  technicianId?: string;
}

export default function InlineVisitScheduler({
  inquiry,
  stateVersion,
  initialDesiredAt = "",
  onBack,
  onStateChange,
}: InlineVisitSchedulerProps) {
  const [technicianId, setTechnicianId] = useState("");
  const [desiredAt, setDesiredAt] = useState(initialDesiredAt);
  const [confirmedAt, setConfirmedAt] = useState("");
  const [errors, setErrors] = useState<ScheduleErrors>({});
  const [currentVersion, setCurrentVersion] = useState(stateVersion);
  const [result, setResult] = useState<"SAVED" | "CONFIRMED" | null>(null);
  const selectedTechnician = MOCK_TECHNICIANS.find(
    (technician) => technician.id === technicianId,
  );

  const submit = (mode: "SAVE" | "CONFIRM") => {
    const nextErrors: ScheduleErrors = {};
    if (!technicianId) nextErrors.technicianId = "방문기사를 선택해 주세요.";
    if (!desiredAt) nextErrors.desiredAt = "고객 희망일을 선택해 주세요.";
    if (mode === "CONFIRM" && !confirmedAt) {
      nextErrors.confirmedAt = "확정 방문일을 선택해 주세요.";
    }
    if (
      mode === "CONFIRM" &&
      desiredAt &&
      confirmedAt &&
      confirmedAt < desiredAt
    ) {
      nextErrors.confirmedAt = "확정 방문일은 고객 희망일보다 빠를 수 없습니다.";
    }

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    const nextVersion = currentVersion + 1;
    const status: CounselorStatus =
      mode === "CONFIRM" ? "VISIT_SCHEDULED" : "VISIT_SCHEDULING";
    setCurrentVersion(nextVersion);
    setResult(mode === "CONFIRM" ? "CONFIRMED" : "SAVED");
    onStateChange({
      status,
      stateVersion: nextVersion,
      allowedActions:
        status === "VISIT_SCHEDULING"
          ? consultantWorkspaceRepository.getAllowedActions(status)
          : [],
    });
  };

  return (
    <section className="simple-visit-scheduler" aria-label="기사 배정 및 일정 조율">
      <header>
        <div>
          <small>FIELD SERVICE · MOCK</small>
          <h3>기사 배정·일정 조율</h3>
          <p>상담 화면을 벗어나지 않고 필요한 일정만 빠르게 확정합니다.</p>
        </div>
        <button type="button" onClick={onBack}>상담 기록 보기</button>
      </header>

      <div className="simple-visit-context">
        <span>방문 사유</span>
        <strong>{inquiry.symptomLabel} · 상담 후 현장 확인 필요</strong>
        <small>{inquiry.usageMessage}</small>
      </div>

      <div className="simple-visit-fields">
        <label>
          <span>방문기사 <b>필수</b></span>
          <select
            aria-label="방문기사"
            value={technicianId}
            aria-invalid={Boolean(errors.technicianId)}
            onChange={(event) => {
              setTechnicianId(event.target.value);
              setErrors((current) => ({ ...current, technicianId: undefined }));
              setResult(null);
            }}
          >
            <option value="">기사를 선택하세요</option>
            {MOCK_TECHNICIANS.map((technician) => (
              <option key={technician.id} value={technician.id}>
                {technician.name} · {technician.team}
              </option>
            ))}
          </select>
          <small>{selectedTechnician ? `담당 권역 · ${selectedTechnician.area}` : errors.technicianId}</small>
        </label>

        <label>
          <span>고객 희망일 <b>필수</b></span>
          <input
            type="datetime-local"
            aria-label="고객 희망일"
            value={desiredAt}
            aria-invalid={Boolean(errors.desiredAt)}
            onChange={(event) => {
              setDesiredAt(event.target.value);
              setErrors((current) => ({ ...current, desiredAt: undefined }));
              setResult(null);
            }}
          />
          <small>{errors.desiredAt}</small>
        </label>

        <label>
          <span>확정 방문일 <b>확정 시 필수</b></span>
          <input
            type="datetime-local"
            aria-label="확정 방문일"
            value={confirmedAt}
            aria-invalid={Boolean(errors.confirmedAt)}
            onChange={(event) => {
              setConfirmedAt(event.target.value);
              setErrors((current) => ({ ...current, confirmedAt: undefined }));
              setResult(null);
            }}
          />
          <small>{errors.confirmedAt}</small>
        </label>
      </div>

      <div className="simple-visit-actions">
        <span>상태 버전 {currentVersion}</span>
        <button type="button" onClick={() => submit("SAVE")}>일정 임시 저장</button>
        <button className="is-primary" type="button" onClick={() => submit("CONFIRM")}>
          기사 배정·방문 확정
        </button>
      </div>

      {result && (
        <p className="simple-action-message is-success" role="status">
          {result === "CONFIRMED"
            ? `${selectedTechnician?.name} 기사 배정과 방문 일정이 확정되었습니다.`
            : "기사와 고객 희망일을 Mock으로 저장했습니다."}
        </p>
      )}
    </section>
  );
}
