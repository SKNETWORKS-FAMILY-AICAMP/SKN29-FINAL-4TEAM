import type {
  CounselorAllowedAction,
  CounselorInquiry,
  CounselorStatus,
} from "../../consultation/model/consultantWorkspaceTypes";

interface InlineVisitSchedulerProps {
  inquiry: CounselorInquiry;
  stateVersion: number;
  initialPreferredDate?: string;
  onBack: () => void;
  onStateChange: (update: {
    status: CounselorStatus;
    stateVersion: number;
    allowedActions: readonly CounselorAllowedAction[];
  }) => void;
}

export default function InlineVisitScheduler({
  inquiry,
  stateVersion,
  onBack,
}: InlineVisitSchedulerProps) {
  return (
    <section className="simple-visit-scheduler" aria-label="기사 배정 및 일정 조율">
      <header>
        <div>
          <small>FIELD SERVICE · API UNAVAILABLE</small>
          <h3>기사 선택·배정 API 미지원</h3>
          <p>
            기사 목록과 배정 API가 없어 신규 기사 선택·배정을 사용할 수 없습니다.
          </p>
        </div>
        <button type="button" onClick={onBack}>상담 기록 보기</button>
      </header>

      <div className="simple-visit-context">
        <span>방문 사유</span>
        <strong>{inquiry.symptomLabel} · 상담 후 현장 확인 필요</strong>
        <small>{inquiry.usageMessage}</small>
      </div>

      <div className="simple-visit-actions">
        <span>상태 버전 {stateVersion}</span>
        <button type="button" disabled>
          기사 선택·배정 비활성화
        </button>
      </div>

      <p className="simple-action-message">
        고정 기사나 로컬 성공 처리로 대체하지 않습니다. Backend API가 제공되면
        활성화됩니다.
      </p>
    </section>
  );
}
