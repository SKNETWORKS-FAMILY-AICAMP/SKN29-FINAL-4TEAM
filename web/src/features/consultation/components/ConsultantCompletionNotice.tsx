import type { InquiryId } from "../../../entities/inquiry/inquiryIdentifiers";
import { readConsultantCompletionNotice } from "../model/consultantCompletionNavigation";
import { getCounselorWorkBucket, STATUS_LABELS } from "../model/consultantWorkspaceModel";
import "./ConsultantCompletionNotice.css";

interface Props {
  navigationState: unknown;
  onOpenInquiry: (inquiryId: InquiryId) => void;
  onDismiss: () => void;
}

export default function ConsultantCompletionNotice({ navigationState, onOpenInquiry, onDismiss }: Props) {
  const notice = readConsultantCompletionNotice(navigationState);
  if (!notice) return null;

  const isCompleted = getCounselorWorkBucket(notice.status) === "COMPLETED";
  return (
    <section className="consultant-completion-notice" aria-label="문의 처리 결과">
      <div role="status">
        <strong>{notice.source === "PHONE_REGISTERED" ? "전화 문의가 등록되었습니다." : "상담 내용이 확정되었습니다."}</strong>
        {!isCompleted && (
          <p>현재 문의 상태는 ‘{STATUS_LABELS[notice.status]}’입니다. 실제 완료 처리 전에는 완료 목록에 표시되지 않습니다.</p>
        )}
      </div>
      <button type="button" onClick={() => onOpenInquiry(notice.inquiryId)}>해당 문의 확인</button>
      <button type="button" aria-label="문의 처리 결과 안내 닫기" onClick={onDismiss}>×</button>
    </section>
  );
}
