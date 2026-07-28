import type { StatusHistoryItem } from "../model/inquiryDetailTypes";

interface StatusHistorySectionProps {
  statusHistory: readonly StatusHistoryItem[];
}

export default function StatusHistorySection({
  statusHistory,
}: StatusHistorySectionProps) {
  return (
    <section className="inquiry-detail__card">
      <h2>상태 이력</h2>

      <ol className="inquiry-detail__history">
        {statusHistory.map((history, index) => (
          <li key={`${history.status}-${history.occurredAt}`}>
            <div className="inquiry-detail__history-index">{index + 1}</div>

            <div>
              <strong>{history.status}</strong>
              <p>{history.event}</p>

              <span>
                {history.actor} · {history.occurredAt}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
