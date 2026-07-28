interface AiSummarySectionProps {
  summary: string;
}

export default function AiSummarySection({
  summary,
}: AiSummarySectionProps) {
  return (
    <section className="inquiry-detail__card">
      <div className="inquiry-detail__card-title">
        <h2>AI 상담 요약</h2>
        <span>AI 초안</span>
      </div>

      <p>{summary}</p>

      <p className="inquiry-detail__helper-text">
        AI가 작성한 초안입니다. 상담사가 확인하고 수정한 뒤 고객 안내에
        사용해야 합니다.
      </p>
    </section>
  );
}
