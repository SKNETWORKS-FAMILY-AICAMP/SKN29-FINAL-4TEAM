import type { EvidenceCardViewModel } from "../../../entities/evidence/evidenceTypes";
import "./EvidenceCard.css";

interface EvidenceCardProps {
  evidence: EvidenceCardViewModel;
}

export default function EvidenceCard({ evidence }: EvidenceCardProps) {
  const metadata = [
    ["문서 버전", evidence.documentVersion],
    ["근거 페이지", `${evidence.page}쪽`],
    ["검증 상태", evidence.verificationLabel],
    ["데이터 분류", evidence.dataClassification],
  ];

  return (
    <article className="common-evidence-card">
      <span className="common-evidence-card__icon" aria-hidden="true">
        공식
        <br />
        매뉴얼
      </span>
      <div className="common-evidence-card__content">
        <span className="common-evidence-card__verified">
          {evidence.verificationLabel}
        </span>
        <h4>{evidence.documentTitle}</h4>
        <p>{evidence.summary}</p>
        <dl className="common-evidence-card__meta">
          {metadata.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="common-evidence-card__actions">
        {evidence.sourceLandingUrl && (
          <a
            href={evidence.sourceLandingUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            공식 출처 보기 ↗
          </a>
        )}
      </div>
    </article>
  );
}
