import PriorityBadge from "../../../common/components/badge/PriorityBadge";
import RiskBadge from "../../../common/components/badge/RiskBadge";
import type { InquiryDetailViewModel } from "../model/inquiryDetailTypes";

interface InquiryHeaderProps {
  inquiry: InquiryDetailViewModel;
  onBack: () => void;
}

export default function InquiryHeader({
  inquiry,
  onBack,
}: InquiryHeaderProps) {
  return (
    <>
      <header className="inquiry-detail__header">
        <div>
          <p className="inquiry-detail__eyebrow">CONS-02</p>
          <h1>문의 상세</h1>
          <p>{inquiry.inquiryId}</p>
        </div>

        <button
          type="button"
          className="inquiry-detail__back-button"
          onClick={onBack}
        >
          목록으로 돌아가기
        </button>
      </header>

      {inquiry.isDanger && (
        <section className="inquiry-detail__danger-alert" role="alert">
          <strong>위험 문의입니다.</strong>

          <p>
            제품 사용 중지를 유지하도록 안내하고 임의 분해나 부품 교체
            방법을 제공하지 마세요.
          </p>
        </section>
      )}

      <section className="inquiry-detail__summary" aria-label="문의 요약">
        <article>
          <span>현재 상태</span>
          <strong>{inquiry.currentStateLabel}</strong>
        </article>

        <article>
          <span>위험도</span>
          <RiskBadge level={inquiry.riskLevel} />
        </article>

        <article>
          <span>우선순위</span>
          <PriorityBadge
            label={inquiry.priorityLabel}
            variant={inquiry.priorityVariant}
          />
        </article>

        <article>
          <span>현재 담당</span>
          <strong>{inquiry.currentAssigneeLabel}</strong>
        </article>
      </section>
    </>
  );
}
