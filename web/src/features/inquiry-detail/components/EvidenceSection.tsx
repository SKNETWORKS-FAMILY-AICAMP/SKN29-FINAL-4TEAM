import type { InquiryEvidenceViewItem } from "../model/inquiryDetailTypes";

interface EvidenceSectionProps {
  evidence: readonly InquiryEvidenceViewItem[];
}

export default function EvidenceSection({
  evidence,
}: EvidenceSectionProps) {
  return (
    <section className="inquiry-detail__card">
      <h2>공식 근거</h2>

      {evidence.length === 0 ? (
        <div className="inquiry-detail__empty">
          <strong>표시할 공식 근거가 없습니다.</strong>

          <p>근거가 없는 경우 AI 초안을 공식 안내처럼 사용하지 마세요.</p>
        </div>
      ) : (
        <div className="inquiry-detail__evidence-list">
          {evidence.map((item) => (
            <article
              key={`${item.documentTitle}-${item.page}`}
              className="inquiry-detail__evidence"
            >
              <div className="inquiry-detail__evidence-header">
                <strong>{item.documentTitle}</strong>
                <span>{item.verificationLabel}</span>
              </div>

              <p>
                {item.revision} · {item.page}페이지
              </p>

              <p>{item.summary}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
