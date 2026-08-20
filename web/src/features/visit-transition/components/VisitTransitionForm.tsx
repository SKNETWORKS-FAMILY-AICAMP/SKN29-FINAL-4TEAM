import type { CounselorInquiry } from "../../consultation/model/consultantWorkspaceTypes";

interface VisitTransitionFormProps {
  inquiry: CounselorInquiry;
  stateVersion: number;
  symptomSummary: string;
}

export default function VisitTransitionForm({
  inquiry,
  stateVersion,
  symptomSummary,
}: VisitTransitionFormProps) {
  return (
    <div className="visit-v13-layout">
      <aside className="visit-v13-context" aria-label="방문 전환 문의 요약">
        <header>
          <small>HANDOFF CONTEXT</small>
          <h2>기사 인계 기준</h2>
          <p>상담에서 확인된 정보만 표시하며 기사 배정을 임의로 생성하지 않습니다.</p>
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
      </aside>

      <section
        className="visit-v13-form-panel visit-v13-access-blocked"
        aria-labelledby="visit-assignment-unavailable-title"
      >
        <header className="visit-v13-form-head">
          <div>
            <small>VISIT ASSIGNMENT · API UNAVAILABLE</small>
            <h2 id="visit-assignment-unavailable-title">
              기사 선택·배정 API 미지원
            </h2>
            <p>
              기사 목록과 배정 API가 없어 신규 기사 선택과 일정 저장을 사용할 수
              없습니다.
            </p>
          </div>
          <span>stateVersion {stateVersion}</span>
        </header>

        <div className="visit-v13-status-card">
          <div>
            <small>기사 배정 상태</small>
            <strong>미지원</strong>
          </div>
          <div>
            <small>선택 기사</small>
            <strong>미배정</strong>
          </div>
          <div>
            <small>처리 방식</small>
            <strong>Backend API 대기</strong>
          </div>
        </div>

        <p className="visit-v13-message">
          고정 기사, 로컬 저장, 성공 메시지로 대체하지 않습니다.
        </p>
        <div className="visit-v13-actions">
          <button type="button" disabled>
            기사 선택·배정 비활성화
          </button>
        </div>
      </section>
    </div>
  );
}
