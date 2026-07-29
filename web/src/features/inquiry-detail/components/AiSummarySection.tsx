import type { InquiryDetailSectionStatus } from "../model/inquiryDetailTypes";
import InquirySectionError from "./InquirySectionError";

interface AiSummarySectionProps {
  summary: string;
  status: InquiryDetailSectionStatus;
}

export default function AiSummarySection({
  summary,
  status,
}: AiSummarySectionProps) {
  return (
    <section className="inquiry-detail__card">
      <div className="inquiry-detail__card-title">
        <h2>AI 상담 요약</h2>
        <span>AI 초안</span>
      </div>

      {status === "error" ? (
        <InquirySectionError
          title="AI 상담 요약을 불러오지 못했습니다."
          description="고객 문의와 공식 근거는 계속 확인할 수 있습니다. AI 초안을 사용하지 말고 상담사가 직접 내용을 확인해 주세요."
        />
      ) : (
        <>
          <p>{summary}</p>

          <p className="inquiry-detail__helper-text">
            AI가 작성한 초안입니다. 상담사가 확인하고 수정한 뒤 고객
            안내에 사용해야 합니다.
          </p>
        </>
      )}
    </section>
  );
}
